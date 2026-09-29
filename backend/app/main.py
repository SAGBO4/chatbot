"""
FastAPI application: startup and shutdown, CORS, rate limiting, access logging, and the routers.

The routes live in app/routers/, one module per topic.
"""
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import settings
from app.database import async_session_maker, init_db
from app.limiter import RateLimitExceeded, _rate_limit_exceeded_handler, limiter
from app.openapi_docs import API_DESCRIPTION, TAGS_METADATA
from app.observability import get_logger, sanitize_url_query, setup_observability
from app.routers import admin, crypto, knowledge, moderation, query, system, tickets, webhooks
from app.services.ai_assistant import AIAssistantService
from app.services.bot_settings_service import BotSettingsService
from app.services.crypto_service import CryptoService
from app.services.telegram_relay import TelegramRelay

logger = get_logger(__name__)


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
    description=API_DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    version=__version__,
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


for module in (system, query, tickets, webhooks, knowledge, moderation, crypto, admin):
    app.include_router(module.router)
