"""Inbound support reply emails: the generic HMAC-signed endpoint and Brevo's batch endpoint."""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Security
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import inbound_email
from app.database import get_db
from app.email_parsing import find_ticket_id
from app.limiter import limiter
from app.models import Ticket
from app.observability import get_logger
from app.openapi_docs import RATE_LIMITED, error_responses
from app.schemas import BrevoBatchResponse, BrevoInboundWebhookRequest, InboundEmailResult, InboundEmailWebhookRequest
from app.security import (
    brevo_alt_token_header,
    brevo_token_header,
    brevo_token_query,
    verify_brevo_inbound_token,
    verify_email_webhook_signature,
    webhook_signature_header,
)

logger = get_logger(__name__)
router = APIRouter(tags=["webhooks"], responses=RATE_LIMITED)

EMAIL_DISABLED = "Email support is disabled (`EMAIL_ENABLED` is false) or the webhook secret is not configured."

# How the single-email endpoint reports the statuses of resolve_inbound_email as HTTP errors. The batch
# endpoint returns them as data instead, so one bad item does not fail the whole batch.
HTTP_ERROR_FOR_STATUS = {
    "unauthorized_sender": 403,
    "no_ticket_reference": 400,
    "empty_body": 400,
    "ticket_not_found": 404,
}


@router.post(
    "/api/webhooks/email-inbound",
    summary="Resolve a ticket from a signed email",
    responses={
        200: {"model": InboundEmailResult, "description": "The ticket was resolved, or had already been (`status`)."},
        **error_responses({
            400: "The subject has no `[Ticket #<id>]` reference, or the reply has no new text.",
            401: "The `X-Webhook-Signature` header is missing or does not match the body.",
            403: "The sender is not in `ALLOWED_SUPPORT_EMAIL_SENDERS`.",
            404: "No such ticket.",
            503: EMAIL_DISABLED,
        }),
    },
)
@limiter.limit("30/minute")
async def handle_inbound_email(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    x_webhook_signature: Optional[str] = Security(webhook_signature_header),
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

    if result["status"] in HTTP_ERROR_FOR_STATUS:
        raise HTTPException(status_code=HTTP_ERROR_FOR_STATUS[result["status"]], detail=result["message"])

    return result


@router.post(
    "/api/webhooks/email-inbound/brevo",
    summary="Resolve tickets from a Brevo inbound batch",
    responses={
        200: {"model": BrevoBatchResponse, "description": "One result per item; a failing item does not fail the batch."},
        **error_responses({
            401: "The shared secret is missing or wrong (checked before the body is read).",
            503: EMAIL_DISABLED,
        }),
    },
)
@limiter.limit("30/minute")
async def handle_brevo_inbound_email(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    token: Optional[str] = Security(brevo_token_query),
    x_webhook_token: Optional[str] = Security(brevo_token_header),
    x_brevo_token: Optional[str] = Security(brevo_alt_token_header),
):
    """
    Resolve tickets from Brevo's Inbound Parsing webhook: a batch (`items[]`) of parsed emails
    authenticated by one shared secret (see `verify_brevo_inbound_token`).

    Each item goes through `inbound_email.resolve_inbound_email` independently: one item's failure is reported
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

    ticket_ids = [find_ticket_id(item.Subject) for item in payload.items]

    # Fetch every referenced ticket in one query instead of one round-trip per item
    preloaded_tickets = {}
    referenced = [ticket_id for ticket_id in ticket_ids if ticket_id]
    if referenced:
        ticket_res = await session.execute(select(Ticket).where(Ticket.id.in_(referenced)))
        preloaded_tickets = {ticket.id: ticket for ticket in ticket_res.scalars().all()}

    results = []
    for item, ticket_id in zip(payload.items, ticket_ids):
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
