import logging
from typing import Optional
from bot.api_client import BackendClient
from bot.ttl_cache import MISSING, TTLCache
from app.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

# The active language, cached briefly and cleared right after a successful language change
_language_cache = TTLCache(30.0)
_KEY = "language"


def invalidate_language_cache() -> None:
    """Forget the cached language so the next call reads it again."""
    _language_cache.clear()


async def get_active_language(backend_client: Optional[BackendClient] = None) -> str:
    """Returns the currently configured bot language, defaulting to French."""
    cached = _language_cache.get(_KEY)
    if cached is not MISSING:
        return cached

    client = backend_client or BackendClient()
    try:
        raw = await client.get_setting("language")
        value = raw if raw in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    except Exception as exc:
        logger.warning("Failed to resolve the active bot language: %s", exc)
        value = DEFAULT_LANGUAGE

    _language_cache.set(_KEY, value)
    return value
