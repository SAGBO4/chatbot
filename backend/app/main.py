import hashlib
import hmac
import re
import logging
import inspect
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, Header, HTTPException, Request, status, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _safe_background_task(coro_fn, *args, **kwargs):
    """Run a background task and log any exception (timeout, network drop...) instead of letting it reach Starlette."""
    try:
        if inspect.iscoroutinefunction(coro_fn):
            await coro_fn(*args, **kwargs)
        else:
            res = coro_fn(*args, **kwargs)
            if inspect.isawaitable(res):
                await res
    except Exception as exc:
        logger.error(
            "Background task %s failed with exception: %s",
            getattr(coro_fn, "__name__", str(coro_fn)),
            exc,
            exc_info=True,
        )

from app.config import settings
from app.observability import SensitiveDataFilter, sanitize_url_query, setup_observability
from app.database import get_db, init_db, async_session_maker
from app.models import Ticket, TicketStatus
from app.telegram_text import escape_telegram_markdown, truncate_telegram_text
from app.schemas import (
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
    WarningCreateRequest,
    WarningResponse,
    WarningListResponse,
    CryptoPriceResponse,
    BotSettingRequest,
    BotSettingResponse,
    WhitelistAddRequest,
    WhitelistEntryResponse,
    WhitelistListResponse,
    WhitelistCheckResponse,
)
from app.services.query_orchestrator import QueryOrchestrator
from app.services.ticket_service import TicketService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.email_service import EmailService
from app.services.telegram_relay import TelegramRelay
from app.services.ai_assistant import AIAssistantService
from app.services.warning_service import WarningService
from app.services.crypto_service import CryptoService
from app.services.bot_settings_service import BotSettingsService, WhitelistService
from app.limiter import limiter, RateLimitExceeded, _rate_limit_exceeded_handler
import httpx

logger.addFilter(SensitiveDataFilter())

TICKET_SUBJECT_REGEX = re.compile(r"Ticket\s*#(\d+)", re.IGNORECASE)


def verify_email_webhook_signature(raw_body: bytes, signature: Optional[str]) -> None:
    """
    Verifies the HMAC-SHA256 signature of an inbound email webhook request.

    Raises HTTPException if the webhook secret is not configured (fail closed),
    the signature header is missing, or the signature does not match.
    """
    if not settings.EMAIL_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email support is disabled (EMAIL_ENABLED=False).",
        )
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


# Zero-width characters must not hide a quote marker (e.g. a zero-width space before ">").
# They are stripped for marker detection only, never from the text that is kept.
_INVISIBLE_CHARS_RE = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")

# Quoted email header line, e.g. "From: support@example.com" or
# "De : Jean <jean@example.com>".
_FROM_PREFIX_RE = re.compile(r"^(?:From|De)\s*:\s*(.*)$", re.IGNORECASE)


def _is_quoted_header_line(text: str) -> bool:
    """
    True if `text` is only a "From:" / "De :" header whose value ends in an email address
    (bare or bracketed). A sentence that merely starts that way and mentions an address
    mid-sentence ("De : notre point de vue <a@b.c>, le souci vient du DNS.") must not match.

    Plain string operations on purpose: a single regex with two overlapping unbounded
    quantifiers backtracked catastrophically (a ~200KB line took 100+ seconds; see the ReDoS test).
    """
    match = _FROM_PREFIX_RE.match(text)
    if not match:
        return False
    remainder = match.group(1).strip()
    if not remainder:
        return False

    if remainder.endswith(">"):
        open_idx = remainder.rfind("<")
        if open_idx == -1:
            return False
        inner = remainder[open_idx + 1 : -1]
        return "@" in inner and "<" not in inner and ">" not in inner

    last_token = remainder.split()[-1]
    return "@" in last_token and not last_token.startswith("@") and not last_token.endswith("@")


def clean_email_reply_body(body: Optional[str]) -> str:
    """
    Strip quoted thread history from an email reply: keep what precedes the first quote marker.

    The result is legitimately empty when the marker is on the first line (bottom-posted reply,
    forward): the reply added no content. Callers must treat "" as "nothing to resolve" and never
    fall back to the raw body, which would leak the quoted thread into the ticket solution and the
    knowledge base. `None` gives ""; any other non-str raises TypeError.
    """
    if body is None:
        return ""
    if not isinstance(body, str):
        raise TypeError(f"clean_email_reply_body expects a str or None, got {type(body).__name__!r}")

    # Split on real line breaks only: str.splitlines() also splits on \x0b, \x0c, \x1c-\x1e, \x85
    # and U+2028/2029, which would cut one sentence into several "lines".
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Detect markers on a copy without invisible characters; the original `line` is what is kept.
        detection_text = _INVISIBLE_CHARS_RE.sub("", stripped)

        # Common email quote markers: standard email quote prefix '>'
        if detection_text.startswith(">"):
            break
        # Common email separator lines: 4+ dashes, underscores, or equals alone on a line
        if re.match(r"^[-_=]{4,}\s*$", detection_text):
            break
        # Standard "Original Message" / "Forwarded message" / French equivalents
        if re.search(r"[-_]{2,}\s*(?:Original Message|Message d'origine|Forwarded message|Message transféré)\s*[-_]{2,}", detection_text, re.IGNORECASE):
            break
        # Apple Mail / standard forwarded message headers
        if re.search(r"^(?:Begin forwarded message|Début du message transféré)\s*:", detection_text, re.IGNORECASE):
            break
        # Quoted reply markers like "On ... wrote:" or "Le ... a écrit :"
        if re.search(r"^(On\s+.+wrote:|Le\s+.+a écrit\s*:)", detection_text, re.IGNORECASE):
            break
        # Quoted email header lines like "From: support@..." or "De : Jean <...>"
        if _is_quoted_header_line(detection_text):
            break
        clean_lines.append(line)
    return "\n".join(clean_lines).strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: log redaction and Sentry (if configured), database schema, the legacy community group seed, and one
    shared HTTP client for the Telegram relay, AI and crypto services. Shutdown closes that client.
    """
    setup_observability("Backend API")
    await init_db()
    if settings.community_group_is_configured():
        async with async_session_maker() as seed_session:
            try:
                await BotSettingsService.seed_legacy_community_group(
                    seed_session, int(settings.TELEGRAM_COMMUNITY_GROUP_ID)
                )
            except Exception as exc:
                logger.warning("Failed to seed legacy community group setting: %s", exc)
    client = httpx.AsyncClient(timeout=15.0)
    app.state.http_client = client
    TelegramRelay.set_shared_client(client)
    AIAssistantService.set_shared_client(client)
    CryptoService.set_shared_client(client)
    try:
        yield
    finally:
        TelegramRelay.set_shared_client(None)
        AIAssistantService.set_shared_client(None)
        CryptoService.set_shared_client(None)
        await client.aclose()


app = FastAPI(
    title="Telegram Support Bot Backend API",
    description="Backend API for telegram support bot with knowledge base, multi-channel ticketing and email sync",
    version="1.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()],
    # Auth uses the X-API-Key header, not cookies, so credentials are never needed. Keeping this
    # False is also what makes the dev default allow_origins=["*"] safe.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def sanitize_access_logging_middleware(request: Request, call_next):
    """Log each request with secrets in the query string redacted (the reverse proxy must do the same: see deploy/)."""
    sanitized_url = sanitize_url_query(str(request.url))
    logger.debug("HTTP %s %s - incoming", request.method, sanitized_url)
    response = await call_next(request)
    logger.info("HTTP %s %s - status %d", request.method, sanitized_url, response.status_code)
    return response


@app.get("/health")
async def health_check(session: AsyncSession = Depends(get_db)):
    """Liveness probe: pings the database and answers 503 if it is unreachable."""
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
@limiter.limit("30/minute")
async def handle_query(
    request: Request,
    payload: QueryRequest,
    session: AsyncSession = Depends(get_db),
):
    """Answer a user's question from the knowledge base (and the optional AI), with a confidence score."""
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
@limiter.limit("10/minute")
async def create_ticket(
    request: Request,
    payload: TicketCreateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    """Open a support ticket; the support team is emailed in the background when email is enabled."""
    ticket = await TicketService.create_ticket(
        session=session,
        user_id=payload.user_id,
        user_handle=payload.user_handle,
        question=payload.question,
        automated_answer=payload.automated_answer,
    )

    if settings.is_email_configured():
        background_tasks.add_task(
            _safe_background_task,
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
    status_filter: Optional[TicketStatus] = None,
    user_id: Optional[int] = Query(default=None, description="Filter tickets by user ID"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """List tickets, optionally filtered by status or `user_id`; paginated."""
    status_val = status_filter.value if status_filter else None
    return await TicketService.get_all_tickets(
        session=session,
        status=status_val,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


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
    parsing the card's text.
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
    user_id: Optional[int] = Query(default=None, description="Optional user ID to enforce ownership scoping"),
    session: AsyncSession = Depends(get_db),
):
    """Get one ticket. With `user_id`, a ticket belonging to another user is reported as not found."""
    ticket = await TicketService.get_ticket(session=session, ticket_id=ticket_id, user_id=user_id)
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
@limiter.limit("15/minute")
async def resolve_ticket(
    request: Request,
    ticket_id: int,
    payload: TicketResolveRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    """
    Resolve a ticket and, by default, add its solution to the knowledge base.

    `is_newly_resolved` is false when another agent had already resolved it.
    """
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

    # If newly resolved on Telegram, inform the email channel if configured
    if newly_resolved and channel.upper() == "TELEGRAM" and settings.is_email_configured():
        background_tasks.add_task(
            _safe_background_task,
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
    auto_commit: bool = True,
    preloaded_ticket: Optional[Ticket] = None,
) -> Dict[str, Any]:
    """
    Resolve a ticket from an inbound support reply email, whichever webhook delivered it
    (the generic HMAC endpoint or Brevo's batch endpoint).

    Extracts the ticket id from the subject, resolves the ticket, forwards the solution to the
    user on Telegram, notifies the support group and feeds the knowledge base.

    Never raises for expected problems: it returns a dict whose `status` is one of
    `unauthorized_sender`, `no_ticket_reference`, `empty_body`, `ticket_not_found`,
    `already_resolved` or `resolved`, so a batch caller can carry on with its other items and a
    single-item caller can map the status to an HTTP error.
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
    clean_solution = truncate_telegram_text(clean_solution, max_length=5000, suffix="")

    ticket, newly_resolved = await TicketService.resolve_ticket(
        session=session,
        ticket_id=ticket_id,
        solution=clean_solution,
        resolved_by=sender,
        resolution_channel="EMAIL",
        add_to_knowledge_base=True,
        auto_commit=auto_commit,
        preloaded_ticket=preloaded_ticket,
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

    # Solution and sender come from an email: escape their Markdown before wrapping them in our own
    # formatting, or an unbalanced `*`, `_` or backtick makes Telegram reject the whole message (400)
    # after the ticket is already marked resolved.
    safe_solution = escape_telegram_markdown(clean_solution)
    safe_sender = escape_telegram_markdown(sender)

    user_text = (
        f"📬 **Réponse de l'équipe support par Email (Ticket #{ticket_id})**\n\n"
        f"{safe_solution}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Traité par : *{safe_sender}*\n"
        f"Merci de votre confiance ! 👋"
    )
    user_text = truncate_telegram_text(user_text, max_length=4000)
    background_tasks.add_task(
        _safe_background_task,
        TelegramRelay.send_message_to_user,
        ticket.user_id,
        user_text,
    )

    # 2. Inform the Telegram Support Group that the ticket was resolved via email
    group_notification = (
        f"✅ **Ticket #{ticket_id} résolu par Email !**\n"
        f"• Par : `{safe_sender}`\n"
        f"• La solution a été transmise à l'utilisateur (`ID: {ticket.user_id}`).\n"
        f"• La base de connaissances a été mise à jour automatiquement."
    )
    background_tasks.add_task(
        _safe_background_task,
        TelegramRelay.notify_support_group,
        group_notification,
    )

    return {
        "status": "resolved",
        "ticket_id": ticket_id,
        "resolved_by": sender,
        "channel": "EMAIL",
    }


def _select_brevo_body(item: BrevoInboundItem) -> str:
    """
    Pick a Brevo item's own quote-stripped extraction when present, else its raw text body.

    Either way `clean_email_reply_body` runs on it afterwards, as a second pass in case Brevo's
    extraction misses a quote marker.
    """
    if item.ExtractedMarkdownMessage and item.ExtractedMarkdownMessage.strip():
        return item.ExtractedMarkdownMessage
    return item.RawTextBody or ""


def verify_brevo_inbound_token(
    token: Optional[str] = None,
    header_token: Optional[str] = None,
) -> None:
    """
    Verify the shared secret sent with every Brevo inbound webhook call, either in an
    `X-Webhook-Token` / `X-Brevo-Token` header or as a `?token=` query parameter.

    Brevo does not sign its requests. The headers keep the token out of HTTP access logs;
    `?token=` remains supported for compatibility.

    Raises HTTPException if the secret is not configured (fail closed), or the token is missing or wrong.
    """
    if not settings.EMAIL_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email support is disabled (EMAIL_ENABLED=False).",
        )
    if not settings.BREVO_INBOUND_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Brevo inbound webhook is not configured (BREVO_INBOUND_SECRET missing).",
        )
    candidate = header_token or token
    if not candidate or not hmac.compare_digest(candidate, settings.BREVO_INBOUND_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token query parameter or header.",
        )


@app.post("/api/webhooks/email-inbound")
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
            result = await _resolve_inbound_email(
                session=session,
                background_tasks=background_tasks,
                sender=item.From.Address,
                subject=item.Subject,
                body=_select_brevo_body(item),
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


@app.post(
    "/api/knowledge/ingest",
    response_model=KnowledgeArticleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("20/minute")
async def ingest_knowledge(
    request: Request,
    payload: KnowledgeIngestRequest,
    session: AsyncSession = Depends(get_db),
):
    """Add a knowledge base article manually."""
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
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """List knowledge base articles; paginated."""
    return await KnowledgeBaseService.get_all_articles(session=session, limit=limit, offset=offset)


@app.post(
    "/api/moderation/warnings",
    response_model=WarningResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def create_warning(
    payload: WarningCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    """Record a moderation warning for a user in a group."""
    return await WarningService.add_warning(
        session=session,
        user_id=payload.user_id,
        group_id=payload.group_id,
        warned_by=payload.warned_by,
        reason=payload.reason,
    )


@app.get(
    "/api/moderation/warnings",
    response_model=WarningListResponse,
    dependencies=[Depends(verify_api_key)],
)
async def list_warnings(
    user_id: int = Query(..., description="Telegram user id to look up warnings for"),
    group_id: int = Query(..., description="Telegram group id the warnings were issued in"),
    session: AsyncSession = Depends(get_db),
):
    """List a user's warnings in a group, with their count."""
    warnings = await WarningService.list_warnings(session=session, user_id=user_id, group_id=group_id)
    return WarningListResponse(count=len(warnings), warnings=warnings)


@app.get(
    "/api/crypto/{symbol}",
    response_model=CryptoPriceResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_crypto_price(symbol: str):
    """Live market data for an asset symbol (e.g. `btc`): 404 for an unknown symbol, 503 when the price provider is down."""
    if CryptoService.resolve_asset_id(symbol) is None:
        raise HTTPException(status_code=404, detail=f"Unknown asset '{symbol}'")

    data = await CryptoService.get_market_data(symbol)
    if data is None:
        raise HTTPException(status_code=503, detail="Crypto market data temporarily unavailable")

    return CryptoPriceResponse(symbol=symbol.lower(), **data)


@app.get(
    "/api/admin/settings/{key}",
    response_model=BotSettingResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_bot_setting(key: str, session: AsyncSession = Depends(get_db)):
    """Read a persisted bot setting."""
    value = await BotSettingsService.get_value(session=session, key=key)
    return BotSettingResponse(key=key, value=value)


@app.put(
    "/api/admin/settings/{key}",
    response_model=BotSettingResponse,
    dependencies=[Depends(verify_api_key)],
)
async def set_bot_setting(
    key: str,
    payload: BotSettingRequest,
    session: AsyncSession = Depends(get_db),
):
    """Create or update a persisted bot setting."""
    setting = await BotSettingsService.set_value(
        session=session, key=key, value=payload.value, updated_by=payload.updated_by
    )
    return BotSettingResponse(key=setting.key, value=setting.value)


@app.post(
    "/api/admin/whitelist",
    response_model=WhitelistEntryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def add_whitelist_entry(
    payload: WhitelistAddRequest,
    session: AsyncSession = Depends(get_db),
):
    """Add a user to the admin whitelist."""
    return await WhitelistService.add(session=session, user_id=payload.user_id, added_by=payload.added_by)


@app.delete(
    "/api/admin/whitelist/{user_id}",
    dependencies=[Depends(verify_api_key)],
)
async def remove_whitelist_entry(user_id: int, session: AsyncSession = Depends(get_db)):
    """Remove a user from the admin whitelist (404 if not listed)."""
    removed = await WhitelistService.remove(session=session, user_id=user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Whitelist entry not found")
    return {"removed": True, "user_id": user_id}


@app.get(
    "/api/admin/whitelist",
    response_model=WhitelistListResponse,
    dependencies=[Depends(verify_api_key)],
)
async def list_whitelist_entries(session: AsyncSession = Depends(get_db)):
    """List the admin whitelist."""
    entries = await WhitelistService.list(session=session)
    return WhitelistListResponse(entries=entries)


@app.get(
    "/api/admin/whitelist/{user_id}/check",
    response_model=WhitelistCheckResponse,
    dependencies=[Depends(verify_api_key)],
)
async def check_whitelist_entry(user_id: int, session: AsyncSession = Depends(get_db)):
    """Whether a user counts as admin: the bot owner always does, everyone else must be whitelisted."""
    is_whitelisted = settings.is_bot_owner(user_id) or await WhitelistService.is_whitelisted(session=session, user_id=user_id)
    return WhitelistCheckResponse(user_id=user_id, is_whitelisted=is_whitelisted)
