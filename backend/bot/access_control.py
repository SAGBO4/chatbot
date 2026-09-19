import time
import logging
from typing import Dict, Optional, Tuple
from app.config import settings
from bot.api_client import BackendClient

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30.0

# Recent whitelist-check results by user_id (same pattern as bot/admin_check.py). Cleared right after
# every /whitelist change, so a cached answer never hides a change made in this process.
_whitelist_cache: Dict[int, Tuple[bool, float]] = {}


def invalidate_whitelist_cache(user_id: Optional[int] = None) -> None:
    """Clears the cached whitelist result for user_id, or the whole cache if None."""
    if user_id is None:
        _whitelist_cache.clear()
    else:
        _whitelist_cache.pop(user_id, None)


async def is_authorized(user_id: int, backend_client: Optional[BackendClient] = None) -> bool:
    """
    Whether user_id may run /setup_community and /language: the bot owner, or a whitelisted admin.

    Managing the whitelist itself is owner-only (see `is_owner`). The owner (from the env) is checked
    first, in memory, so owner authority never depends on whitelist data; the whitelist lookup is
    cached for 30 seconds.
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


def is_owner(user_id: int) -> bool:
    """Whether user_id is the bot owner from the env, the only user who can manage the whitelist."""
    return settings.is_bot_owner(user_id)
