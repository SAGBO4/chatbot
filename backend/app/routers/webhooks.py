"""Inbound support reply emails: the generic HMAC-signed endpoint and Brevo's batch endpoint."""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import inbound_email
from app.database import get_db
from app.email_parsing import TICKET_SUBJECT_REGEX
from app.limiter import limiter
from app.models import Ticket
from app.observability import get_logger
from app.schemas import BrevoInboundWebhookRequest, InboundEmailWebhookRequest
from app.security import verify_brevo_inbound_token, verify_email_webhook_signature

logger = get_logger(__name__)
router = APIRouter(tags=["webhooks"])


@router.post("/api/webhooks/email-inbound")
@limiter.limit("30/minute")
async def handle_inbound_email(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    x_webhook_signature: Optional[str] = Header(default=None),
):
    """
    Resolve a ticket from a support reply email (ticket id taken from the subject, `[Ticket #123]`).

    The request must carry a hex HMAC-SHA256 of the raw body in `X-Webhook-Signature`, keyed with
    EMAIL_WEBHOOK_SECRET, so only the trusted email relay can resolve tickets and feed the knowledge base.
    """
    raw_body = await request.body()
    verify_email_webhook_signature(raw_body, x_webhook_signature)

    try:
        payload = InboundEmailWebhookRequest.model_validate_json(raw_body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())

    result = await inbound_email.resolve_inbound_email(
        session=session,
        background_tasks=background_tasks,
        sender=payload.sender,
        subject=payload.subject,
        body=payload.body,
    )

    if result["status"] == "unauthorized_sender":
        raise HTTPException(status_code=403, detail=result["message"])
    if result["status"] == "no_ticket_reference":
        raise HTTPException(status_code=400, detail=result["message"])
    if result["status"] == "ticket_not_found":
        raise HTTPException(status_code=404, detail=result["message"])
    if result["status"] == "empty_body":
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.post("/api/webhooks/email-inbound/brevo")
@limiter.limit("30/minute")
async def handle_brevo_inbound_email(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    token: Optional[str] = None,
    x_webhook_token: Optional[str] = Header(default=None),
    x_brevo_token: Optional[str] = Header(default=None),
):
    """
    Resolve tickets from Brevo's Inbound Parsing webhook: a batch (`items[]`) of parsed emails
    authenticated by one shared secret (see `verify_brevo_inbound_token`).

    Each item goes through `_resolve_inbound_email` independently: one item's failure is reported
    in its own result entry and does not abort the batch.

    The token is checked before the body is parsed (manual `model_validate_json` instead of a
    `payload` parameter) so an unauthenticated caller gets a 401, not a 422 revealing the expected JSON.
    """
    header_token = x_webhook_token or x_brevo_token
    verify_brevo_inbound_token(token=token, header_token=header_token)

    raw_body = await request.body()
    try:
        payload = BrevoInboundWebhookRequest.model_validate_json(raw_body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())

    # Batch pre-fetch candidate tickets in one query to avoid sequential round-trips
    candidate_ticket_ids = []
    for item in payload.items:
        match = TICKET_SUBJECT_REGEX.search(item.Subject or "")
        if match:
            candidate_ticket_ids.append(int(match.group(1)))

    preloaded_tickets = {}
    if candidate_ticket_ids:
        ticket_stmt = select(Ticket).where(Ticket.id.in_(candidate_ticket_ids))
        ticket_res = await session.execute(ticket_stmt)
        for t in ticket_res.scalars().all():
            preloaded_tickets[t.id] = t

    results = []
    for item in payload.items:
        match = TICKET_SUBJECT_REGEX.search(item.Subject or "")
        ticket_id = int(match.group(1)) if match else None
        preloaded = preloaded_tickets.get(ticket_id) if ticket_id else None

        try:
            result = await inbound_email.resolve_inbound_email(
                session=session,
                background_tasks=background_tasks,
                sender=item.From.Address,
                subject=item.Subject,
                body=inbound_email.select_brevo_body(item),
                auto_commit=True,
                preloaded_ticket=preloaded,
            )
        except Exception as exc:
            logger.error("Error resolving Brevo batch item for ticket %s: %s", ticket_id, exc)
            result = {
                "status": "internal_error",
                "ticket_id": ticket_id,
                "message": "Unexpected error processing this item; see the server logs.",
            }
        results.append(result)

    return {"results": results}
