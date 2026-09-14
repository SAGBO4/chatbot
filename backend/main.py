import hashlib
import hmac
import re
import logging
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, Header, HTTPException, Request, status, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from backend.config import settings
from backend.database import get_db, init_db
from backend.schemas import (
    QueryRequest,
    QueryResponse,
    TicketCreateRequest,
    TicketResponse,
    TicketResolveRequest,
    TicketSupportCardRequest,
    KnowledgeIngestRequest,
    KnowledgeArticleResponse,
    InboundEmailWebhookRequest,
    BrevoInboundWebhookRequest,
    BrevoInboundItem,
)
from backend.services.query_orchestrator import QueryOrchestrator
from backend.services.ticket_service import TicketService
from backend.services.knowledge_base import KnowledgeBaseService
from backend.services.email_service import EmailService
from backend.services.telegram_relay import TelegramRelay
from backend.services.ai_assistant import AIAssistantService
import httpx

TICKET_SUBJECT_REGEX = re.compile(r"Ticket\s*#(\d+)", re.IGNORECASE)


def verify_email_webhook_signature(raw_body: bytes, signature: Optional[str]) -> None:
    """
    Verifies the HMAC-SHA256 signature of an inbound email webhook request.

    Raises HTTPException if the webhook secret is not configured (fail closed),
    the signature header is missing, or the signature does not match.
    """
    if not settings.EMAIL_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email webhook is not configured (EMAIL_WEBHOOK_SECRET missing).",
        )
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Webhook-Signature header.",
        )
    sig = signature.strip()
    if sig.lower().startswith("sha256="):
        sig = sig.split("=", 1)[1].strip()
    expected = hmac.new(
        settings.EMAIL_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, sig.lower()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """
    Verifies the shared API key sent by trusted callers (the Telegram bot).

    Raises HTTPException if the API key is not configured (fail closed, so
    the backend cannot be deployed unprotected by omission), the header is
    missing, or it does not match.
    """
    if not settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend API is not configured (API_KEY missing).",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header.",
        )


def clean_email_reply_body(body: str) -> str:
    """
    Strips email thread history and quote lines.

    Returns whatever precedes the first quote marker, which is legitimately
    empty when the marker sits on the first line (bottom-posted replies,
    forwards, some Brevo payloads whose extraction fell back to the raw
    text) - i.e. the reply added no new content of its own. Callers must
    treat an empty result as "nothing to resolve with" rather than falling
    back to the untouched body, which would leak the quoted thread history
    back into the ticket solution and the knowledge base.
    """
    lines = body.splitlines()
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Common email quote markers (standard, dashes, and Outlook underscores)
        if stripped.startswith(">") or stripped.startswith("---") or stripped.startswith("___"):
            break
        if re.search(r"^(On\s+.+wrote:|Le\s+.+a écrit\s*:|(?:From|De)\s*:)", stripped, re.IGNORECASE):
            break
        clean_lines.append(line)
    return "\n".join(clean_lines).strip()


def escape_telegram_markdown(text: str) -> str:
    """Escapes legacy Telegram Markdown metacharacters in untrusted text."""
    return re.sub(r"([_*`\[])", r"\\\1", text)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    client = httpx.AsyncClient(timeout=15.0)
    app.state.http_client = client
    TelegramRelay.set_shared_client(client)
    AIAssistantService.set_shared_client(client)
    try:
        yield
    finally:
        TelegramRelay.set_shared_client(None)
        AIAssistantService.set_shared_client(None)
        await client.aclose()


app = FastAPI(
    title="Telegram Support Bot Backend API",
    description="Backend API for telegram support bot with knowledge base, multi-channel ticketing and email sync",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()],
    # No cookie/session-based auth is used (see verify_api_key: X-API-Key
    # header), so credentialed CORS requests are never needed. Keeping this
    # False is also what makes allow_origins=["*"] (the local/dev default)
    # safe - browsers refuse "*" together with allow_credentials=True.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check(session: AsyncSession = Depends(get_db)):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected", "service": "support-bot-backend"}
    except Exception as exc:
        logger.error("Health check database connectivity failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connectivity error",
        )


@app.post("/api/query", response_model=QueryResponse, dependencies=[Depends(verify_api_key)])
async def handle_query(
    payload: QueryRequest,
    session: AsyncSession = Depends(get_db),
):
    return await QueryOrchestrator.process_query(
        session=session,
        query=payload.query,
        user_id=payload.user_id,
        user_handle=payload.user_handle,
    )


@app.post(
    "/api/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def create_ticket(
    payload: TicketCreateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    ticket = await TicketService.create_ticket(
        session=session,
        user_id=payload.user_id,
        user_handle=payload.user_handle,
        question=payload.question,
        automated_answer=payload.automated_answer,
    )

    # Multi-channel alert: dispatch email notification to support team in the background
    background_tasks.add_task(
        EmailService.send_ticket_created_notification,
        ticket_id=ticket.id,
        user_handle=ticket.user_handle,
        user_id=ticket.user_id,
        question=ticket.question,
        automated_answer=ticket.automated_answer,
    )

    return ticket


@app.get("/api/tickets", response_model=List[TicketResponse], dependencies=[Depends(verify_api_key)])
async def list_tickets(
    status_filter: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    return await TicketService.get_all_tickets(session=session, status=status_filter, limit=limit, offset=offset)


@app.get(
    "/api/tickets/by-support-message/{message_id}",
    response_model=TicketResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_ticket_by_support_message(
    message_id: int,
    session: AsyncSession = Depends(get_db),
):
    """
    Looks up a ticket by the Telegram message id of its support-group card,
    so an agent's reply can be matched by message identity rather than by
    parsing the card's text (see openspec change harden-support-reply-ticket-lookup).
    """
    ticket = await TicketService.get_ticket_by_support_message_id(
        session=session, message_id=message_id
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="No ticket found for this support message id")
    return ticket


@app.get(
    "/api/tickets/{ticket_id}",
    response_model=TicketResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_ticket(
    ticket_id: int,
    session: AsyncSession = Depends(get_db),
):
    ticket = await TicketService.get_ticket(session=session, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.post(
    "/api/tickets/{ticket_id}/support-card",
    response_model=TicketResponse,
    dependencies=[Depends(verify_api_key)],
)
async def attach_support_card(
    ticket_id: int,
    payload: TicketSupportCardRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Records the Telegram message id of the ticket card posted to the Support
    Group, so a later agent reply can be resolved by message identity.
    """
    ticket = await TicketService.attach_support_card(
        session=session, ticket_id=ticket_id, message_id=payload.message_id
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.post(
    "/api/tickets/{ticket_id}/resolve",
    response_model=TicketResponse,
    dependencies=[Depends(verify_api_key)],
)
async def resolve_ticket(
    ticket_id: int,
    payload: TicketResolveRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    channel = payload.resolution_channel or "TELEGRAM"
    ticket, newly_resolved = await TicketService.resolve_ticket(
        session=session,
        ticket_id=ticket_id,
        solution=payload.solution,
        resolved_by=payload.resolved_by,
        resolution_channel=channel,
        add_to_knowledge_base=payload.add_to_knowledge_base,
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # If newly resolved on Telegram, inform the email channel
    if newly_resolved and channel.upper() == "TELEGRAM":
        background_tasks.add_task(
            EmailService.send_ticket_resolved_notification,
            ticket_id=ticket.id,
            resolved_by=ticket.resolved_by,
            resolution_channel="TELEGRAM",
            solution=ticket.solution,
        )

    res = TicketResponse.model_validate(ticket)
    res.is_newly_resolved = newly_resolved
    return res


async def _resolve_inbound_email(
    session: AsyncSession,
    background_tasks: BackgroundTasks,
    sender: str,
    subject: str,
    body: str,
) -> Dict[str, Any]:
    """
    Shared resolution logic for an inbound support reply email, regardless of
    which webhook shape delivered it (generic HMAC-signed endpoint or Brevo's
    native Inbound Parsing endpoint).

    Extracts the ticket id from the subject, resolves the ticket, forwards the
    solution to the user on Telegram, notifies the support group, and feeds
    the knowledge base. Never raises for a missing/unmatched ticket id or an
    unknown ticket id - both are reported back as a result dict so a caller
    processing a batch (Brevo) can continue with its other items; a caller
    with a single-item contract (the generic endpoint) can still translate
    these into its existing HTTPException responses.
    """
    if not settings.is_authorized_email_sender(sender):
        return {
            "status": "unauthorized_sender",
            "ticket_id": None,
            "message": f"Sender '{sender}' is not authorized to resolve tickets via email.",
        }

    match = TICKET_SUBJECT_REGEX.search(subject)
    if not match:
        return {
            "status": "no_ticket_reference",
            "ticket_id": None,
            "message": "Could not identify Ticket ID in email subject (expected '[Ticket #123]').",
        }

    ticket_id = int(match.group(1))
    clean_solution = clean_email_reply_body(body)

    if not clean_solution:
        return {
            "status": "empty_body",
            "ticket_id": ticket_id,
            "message": (
                f"Email reply for Ticket #{ticket_id} had no content once quoted "
                "thread history was stripped; ticket left unresolved."
            ),
        }

    # Cap solution to max 5000 chars matching TicketResolveRequest constraint
    if len(clean_solution) > 5000:
        clean_solution = clean_solution[:5000]

    ticket, newly_resolved = await TicketService.resolve_ticket(
        session=session,
        ticket_id=ticket_id,
        solution=clean_solution,
        resolved_by=sender,
        resolution_channel="EMAIL",
        add_to_knowledge_base=True,
    )

    if not ticket:
        return {
            "status": "ticket_not_found",
            "ticket_id": ticket_id,
            "message": f"Ticket #{ticket_id} not found.",
        }

    if not newly_resolved:
        return {
            "status": "already_resolved",
            "ticket_id": ticket_id,
            "message": f"Ticket #{ticket_id} was already resolved by {ticket.resolved_by} via {ticket.resolution_channel}.",
        }

    # 1. Forward the solution to the user on Telegram. The solution and sender
    # come straight from an inbound email, so any Markdown metacharacter they
    # contain must be escaped before being wrapped in our own ** / * / ` -
    # otherwise an unbalanced '*', '_' or '`' makes Telegram reject the whole
    # message with a 400 after the ticket has already been marked resolved.
    safe_solution = escape_telegram_markdown(clean_solution)
    safe_sender = escape_telegram_markdown(sender)

    user_text = (
        f"📬 **Réponse de l'équipe support par Email (Ticket #{ticket_id})**\n\n"
        f"{safe_solution}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Traité par : *{safe_sender}*\n"
        f"Merci de votre confiance ! 👋"
    )
    background_tasks.add_task(TelegramRelay.send_message_to_user, ticket.user_id, user_text)

    # 2. Inform the Telegram Support Group that the ticket was resolved via email
    group_notification = (
        f"✅ **Ticket #{ticket_id} résolu par Email !**\n"
        f"• Par : `{safe_sender}`\n"
        f"• La solution a été transmise à l'utilisateur (`ID: {ticket.user_id}`).\n"
        f"• La base de connaissances a été mise à jour automatiquement."
    )
    background_tasks.add_task(TelegramRelay.notify_support_group, group_notification)

    return {
        "status": "resolved",
        "ticket_id": ticket_id,
        "resolved_by": sender,
        "channel": "EMAIL",
    }


def _select_brevo_body(item: BrevoInboundItem) -> str:
    """
    Picks the best available body from a Brevo Inbound Parsing item: its own
    signature/quote-stripped extraction when present, else the raw text body.
    Either way the result still passes through clean_email_reply_body as a
    second pass, so behavior degrades gracefully if Brevo's extraction ever
    misses a quote marker our own regex still catches.
    """
    if item.ExtractedMarkdownMessage and item.ExtractedMarkdownMessage.strip():
        return item.ExtractedMarkdownMessage
    return item.RawTextBody or ""


def verify_brevo_inbound_token(token: Optional[str]) -> None:
    """
    Verifies the shared secret Brevo sends back as a `?token=` query
    parameter on every call to the Brevo inbound webhook.

    Brevo does not sign its webhook requests or support a custom header, so a
    secret embedded in the URL is the only practical authentication - see
    openspec/changes/add-brevo-inbound-email-webhook/design.md.

    Raises HTTPException if the secret is not configured (fail closed), the
    token is missing, or it does not match.
    """
    if not settings.BREVO_INBOUND_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Brevo inbound webhook is not configured (BREVO_INBOUND_SECRET missing).",
        )
    if not token or not hmac.compare_digest(token, settings.BREVO_INBOUND_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token query parameter.",
        )


@app.post("/api/webhooks/email-inbound")
async def handle_inbound_email(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    x_webhook_signature: Optional[str] = Header(default=None),
):
    """
    Handles incoming support reply emails.
    Extracts ticket ID from subject ([Ticket #123]), resolves the ticket,
    delivers the answer to the user on Telegram, and updates the knowledge base.

    The request must carry a valid HMAC-SHA256 signature of the raw body
    (header X-Webhook-Signature, hex-encoded, keyed with EMAIL_WEBHOOK_SECRET)
    so that only the trusted email relay can create/resolve tickets and feed
    the knowledge base.
    """
    raw_body = await request.body()
    verify_email_webhook_signature(raw_body, x_webhook_signature)

    try:
        payload = InboundEmailWebhookRequest.model_validate_json(raw_body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())

    result = await _resolve_inbound_email(
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


@app.post("/api/webhooks/email-inbound/brevo")
async def handle_brevo_inbound_email(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    token: Optional[str] = None,
):
    """
    Handles Brevo's native Inbound Parsing webhook shape: a batch (`items[]`)
    of parsed emails, each authenticated collectively by a shared secret sent
    as a `?token=` query parameter (Brevo signs nothing itself - see
    verify_brevo_inbound_token).

    Every item is resolved independently via the same logic as the generic
    /api/webhooks/email-inbound endpoint (_resolve_inbound_email): one item's
    failure (no ticket id in its subject, unknown ticket) is reported in that
    item's result entry without aborting the rest of the batch.

    The token is checked before the body is parsed (raw bytes -> manual
    model_validate_json, same as the generic endpoint) rather than via a
    `payload: BrevoInboundWebhookRequest` parameter, so an unauthenticated
    caller gets a plain 401 instead of a 422 disclosing the expected JSON
    shape.
    """
    verify_brevo_inbound_token(token)

    raw_body = await request.body()
    try:
        payload = BrevoInboundWebhookRequest.model_validate_json(raw_body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())

    results = []
    for item in payload.items:
        result = await _resolve_inbound_email(
            session=session,
            background_tasks=background_tasks,
            sender=item.From.Address,
            subject=item.Subject,
            body=_select_brevo_body(item),
        )
        results.append(result)

    return {"results": results}


@app.post(
    "/api/knowledge/ingest",
    response_model=KnowledgeArticleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def ingest_knowledge(
    payload: KnowledgeIngestRequest,
    session: AsyncSession = Depends(get_db),
):
    return await KnowledgeBaseService.add_article(
        session=session,
        question=payload.question,
        solution=payload.solution,
        keywords=payload.keywords,
        source_ticket_id=payload.source_ticket_id,
    )


@app.get(
    "/api/knowledge",
    response_model=List[KnowledgeArticleResponse],
    dependencies=[Depends(verify_api_key)],
)
async def list_knowledge(
    session: AsyncSession = Depends(get_db),
):
    return await KnowledgeBaseService.get_all_articles(session=session)
