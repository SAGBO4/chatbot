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


def sanitize_url_query(url: str) -> str:
    """
    Redacts values of sensitive query parameters (such as token, secret, api_key)
    from URL strings so they are never printed in access logs or debug traces.
    """
    return re.sub(
        r"([?&](?:token|secret|api_key|password)=)[^&]+",
        r"\1[REDACTED]",
        url,
        flags=re.IGNORECASE,
    )


class SensitiveDataFilter(logging.Filter):
    """
    Log filter that intercepts and redacts sensitive query parameters (e.g. ?token=...)
    from log records and arguments, preventing credential leakage in log files.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_url_query(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    sanitize_url_query(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: sanitize_url_query(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
        return True


logger.addFilter(SensitiveDataFilter())


async def _safe_background_task(coro_fn, *args, **kwargs):
    """
    Executes a background task inside an isolated fault boundary so that any
    unhandled exception (socket timeout, network drop, etc.) is logged with
    full context and does not propagate to Starlette's ASGI response serialization loop.
    """
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

from backend.config import settings
from backend.database import get_db, init_db, async_session_maker
from backend.models import Ticket, TicketStatus
from bot.utils import escape_telegram_markdown, truncate_telegram_text
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
from backend.services.query_orchestrator import QueryOrchestrator
from backend.services.ticket_service import TicketService
from backend.services.knowledge_base import KnowledgeBaseService
from backend.services.email_service import EmailService
from backend.services.telegram_relay import TelegramRelay
from backend.services.ai_assistant import AIAssistantService
from backend.services.warning_service import WarningService
from backend.services.crypto_service import CryptoService
from backend.services.bot_settings_service import BotSettingsService, WhitelistService
from backend.limiter import limiter, RateLimitExceeded, _rate_limit_exceeded_handler
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


# Zero-width / invisible formatting characters that must never be able to
# mask a quote marker (e.g. a zero-width space slipped in front of '>' -
# accidentally by a mail client, or deliberately - would otherwise defeat
# every check below and leak quoted thread history into the ticket solution
# and the knowledge base). Stripped only for marker *detection*; the
# original line text is what actually gets kept in clean_lines, so this
# never alters real content.
_INVISIBLE_CHARS_RE = re.compile("[​‌‍⁠﻿]")

# Quoted email header line, e.g. "From: support@example.com" or
# "De : Jean <jean@example.com>".
_FROM_PREFIX_RE = re.compile(r"^(?:From|De)\s*:\s*(.*)$", re.IGNORECASE)


def _is_quoted_header_line(text: str) -> bool:
    """
    True if `text` is (only) a "From:"/"De :" header whose value ends in an
    email address, bare or bracketed - not merely a sentence that starts
    that way and happens to mention an address mid-sentence, e.g. "De :
    notre point de vue technique <support@example.com>, le souci vient du
    DNS." must NOT match.

    Deliberately implemented with plain string operations instead of a
    single regex: an earlier version used `.*(?:<...@...>|\\S+@\\S+)\\s*$`,
    which has two unbounded, overlapping quantifiers (`.*` and `\\S+`) and
    is vulnerable to catastrophic backtracking (confirmed by a dedicated
    ReDoS test - a ~200KB non-matching line took 100+ seconds). This
    formulation only ever does bounded, linear work.
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
    Strips email thread history and quote lines.

    Returns whatever precedes the first quote marker, which is legitimately
    empty when the marker sits on the first line (bottom-posted replies,
    forwards, some Brevo payloads whose extraction fell back to the raw
    text) - i.e. the reply added no new content of its own. Callers must
    treat an empty result as "nothing to resolve with" rather than falling
    back to the untouched body, which would leak the quoted thread history
    back into the ticket solution and the knowledge base.

    `body` is normally a str (guaranteed by the Pydantic request schemas of
    every current caller), but this is a small reusable text helper, not a
    request handler, so it validates its own input rather than trusting
    every future caller: None is treated as "no content" (returns "",
    consistent with the "nothing to resolve" contract above), and any other
    non-str type raises TypeError immediately instead of failing later with
    a confusing AttributeError/TypeError deep inside the loop.
    """
    if body is None:
        return ""
    if not isinstance(body, str):
        raise TypeError(f"clean_email_reply_body expects a str or None, got {type(body).__name__!r}")

    # Split strictly on real line breaks (\r\n, \r, \n) - NOT str.splitlines(),
    # which also treats \x0b, \x0c, \x1c-\x1e, \x85 (NEL), U+2028 and U+2029
    # as line boundaries and can fragment one legitimate sentence into
    # multiple independently-matched "lines".
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Marker detection is done on a copy with invisible characters
        # stripped out, so they can't be used to smuggle a marker past these
        # checks; `line` (unmodified) is still what gets appended below.
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
    if getattr(settings, "SENTRY_DSN", None):
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=1.0)
            logger.info("Sentry monitoring initialized for Backend API.")
        except ImportError:
            logger.warning("SENTRY_DSN is configured but sentry_sdk is not installed.")
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
    # No cookie/session-based auth is used (see verify_api_key: X-API-Key
    # header), so credentialed CORS requests are never needed. Keeping this
    # False is also what makes allow_origins=["*"] (the local/dev default)
    # safe - browsers refuse "*" together with allow_credentials=True.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# REVERSE PROXY ACCESS LOGGING GUIDANCE:
# To prevent sensitive query tokens (?token=...) from leaking into server access logs:
# - Nginx: log $uri instead of $request_uri, or configure map to redact query strings:
#     log_format safe '$remote_addr - $remote_user [$time_local] "$request_method $uri" $status $body_bytes_sent';
# - Caddy: configure log filtering or pass tokens via X-Webhook-Token header instead of URL queries.
@app.middleware("http")
async def sanitize_access_logging_middleware(request: Request, call_next):
    sanitized_url = sanitize_url_query(str(request.url))
    logger.debug("HTTP %s %s - incoming", request.method, sanitized_url)
    response = await call_next(request)
    logger.info("HTTP %s %s - status %d", request.method, sanitized_url, response.status_code)
    return response


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
@limiter.limit("30/minute")
async def handle_query(
    request: Request,
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
@limiter.limit("10/minute")
async def create_ticket(
    request: Request,
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
    user_id: Optional[int] = Query(default=None, description="Optional user ID to enforce ownership scoping"),
    session: AsyncSession = Depends(get_db),
):
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
    Picks the best available body from a Brevo Inbound Parsing item: its own
    signature/quote-stripped extraction when present, else the raw text body.
    Either way the result still passes through clean_email_reply_body as a
    second pass, so behavior degrades gracefully if Brevo's extraction ever
    misses a quote marker our own regex still catches.
    """
    if item.ExtractedMarkdownMessage and item.ExtractedMarkdownMessage.strip():
        return item.ExtractedMarkdownMessage
    return item.RawTextBody or ""


def verify_brevo_inbound_token(
    token: Optional[str] = None,
    header_token: Optional[str] = None,
) -> None:
    """
    Verifies the shared secret Brevo sends back either via an X-Webhook-Token /
    X-Brevo-Token header or as a `?token=` query parameter on every call to the
    Brevo inbound webhook.

    Brevo does not sign its webhook requests natively. Authenticating via custom
    headers (X-Webhook-Token or X-Brevo-Token) avoids leaking tokens in HTTP
    access logs, while maintaining backward-compatible support for `?token=...`.

    Raises HTTPException if the secret is not configured (fail closed), the
    token is missing, or it does not match.
    """
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
    x_webhook_token: Optional[str] = Header(default=None),
    x_brevo_token: Optional[str] = Header(default=None),
):
    """
    Handles Brevo's native Inbound Parsing webhook shape: a batch (`items[]`)
    of parsed emails, each authenticated collectively by a shared secret sent
    either via `X-Webhook-Token` / `X-Brevo-Token` headers or as a `?token=`
    query parameter.

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
                "message": f"Unexpected error processing item: {exc}",
            }
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
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
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
    warnings = await WarningService.list_warnings(session=session, user_id=user_id, group_id=group_id)
    return WarningListResponse(count=len(warnings), warnings=warnings)


@app.get(
    "/api/crypto/{symbol}",
    response_model=CryptoPriceResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_crypto_price(symbol: str):
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
    return await WhitelistService.add(session=session, user_id=payload.user_id, added_by=payload.added_by)


@app.delete(
    "/api/admin/whitelist/{user_id}",
    dependencies=[Depends(verify_api_key)],
)
async def remove_whitelist_entry(user_id: int, session: AsyncSession = Depends(get_db)):
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
    entries = await WhitelistService.list(session=session)
    return WhitelistListResponse(entries=entries)


@app.get(
    "/api/admin/whitelist/{user_id}/check",
    response_model=WhitelistCheckResponse,
    dependencies=[Depends(verify_api_key)],
)
async def check_whitelist_entry(user_id: int, session: AsyncSession = Depends(get_db)):
    is_whitelisted = await WhitelistService.is_whitelisted(session=session, user_id=user_id)
    return WhitelistCheckResponse(user_id=user_id, is_whitelisted=is_whitelisted)
