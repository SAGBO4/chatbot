import time
import logging
from typing import Dict, Optional, Tuple
from app.config import settings
from bot.api_client import BackendClient

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30.0

# In-memory cache of recent whitelist-check results, keyed by user_id.
# Mirrors bot/admin_check.py's pattern. Eagerly invalidated by
# invalidate_whitelist_cache() right after a successful /whitelist change,
# so a cache hit never masks a just-made change in the same process.
_whitelist_cache: Dict[int, Tuple[bool, float]] = {}


def invalidate_whitelist_cache(user_id: Optional[int] = None) -> None:
    """Clears the cached whitelist result for user_id, or the whole cache if None."""
    if user_id is None:
        _whitelist_cache.clear()
    else:
        _whitelist_cache.pop(user_id, None)


async def is_authorized(user_id: int, backend_client: Optional[BackendClient] = None) -> bool:
    """
    Whether user_id may configure the community group, manage the whitelist
    entry point, or change the bot language.

    Checks the env-defined owner id first (a plain in-memory comparison, no
    I/O, so owner authority can never be affected by whitelist data
    corruption), then falls back to a short-TTL cached whitelist lookup.
    """
    if settings.is_bot_owner(user_id):
        return True

    cached = _whitelist_cache.get(user_id)
    now = time.time()
    if cached is not None and (now - cached[1]) < _CACHE_TTL_SECONDS:
        return cached[0]

    client = backend_client or BackendClient()
    try:
        result = await client.is_whitelisted(user_id)
    except Exception as exc:
        logger.warning("Failed to check whitelist status for user %s: %s", user_id, exc)
        result = False

    _whitelist_cache[user_id] = (result, now)
    return result


async def is_owner(user_id: int) -> bool:
    return settings.is_bot_owner(user_id)
