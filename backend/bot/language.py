import time
import logging
from typing import Optional, Tuple
from bot.api_client import BackendClient
from bot.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30.0

# Same cache pattern as bot/group_scope.py: short TTL, cleared right after a successful language change.
_cached_language: Optional[Tuple[str, float]] = None


def invalidate_language_cache() -> None:
    """Forget the cached language so the next call reads it again."""
    global _cached_language
    _cached_language = None


async def get_active_language(backend_client: Optional[BackendClient] = None) -> str:
    """Returns the currently configured bot language, defaulting to French."""
    global _cached_language
    now = time.time()
    if _cached_language is not None:
        value, fetched_at = _cached_language
        if (now - fetched_at) < _CACHE_TTL_SECONDS:
            return value

    client = backend_client or BackendClient()
    try:
        raw = await client.get_setting("language")
        value = raw if raw in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    except Exception as exc:
        logger.warning("Failed to resolve the active bot language: %s", exc)
        value = DEFAULT_LANGUAGE

    _cached_language = (value, now)
    return value
