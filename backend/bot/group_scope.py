import time
import logging
from typing import Optional, Tuple, Union
from bot.api_client import BackendClient

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30.0

# The persisted community group id, cached briefly (same pattern as bot/admin_check.py). Cleared right
# after a successful /setup_community so this process sees the change without waiting for the TTL.
_cached_community_group_id: Optional[Tuple[Optional[int], float]] = None


def invalidate_community_group_cache() -> None:
    """Forget the cached community group id so the next call reads it again."""
    global _cached_community_group_id
    _cached_community_group_id = None


async def get_community_group_id(backend_client: Optional[BackendClient] = None) -> Optional[int]:
    """Returns the currently configured community group id, or None if unset."""
    global _cached_community_group_id
    now = time.time()
    if _cached_community_group_id is not None:
        value, fetched_at = _cached_community_group_id
        if (now - fetched_at) < _CACHE_TTL_SECONDS:
            return value

    client = backend_client or BackendClient()
    try:
        raw = await client.get_setting("community_group_id")
        value = int(raw) if raw is not None else None
    except Exception as exc:
        logger.warning("Failed to resolve the configured community group id: %s", exc)
        value = None

    _cached_community_group_id = (value, now)
    return value


async def is_community_group_chat(
    chat_id: Union[int, str], backend_client: Optional[BackendClient] = None
) -> bool:
    """
    True only if chat_id is the configured community group (read from the persisted setting, not the
    env). False while none is configured, so an unconfigured bot never matches.
    """
    community_group_id = await get_community_group_id(backend_client=backend_client)
    if community_group_id is None:
        return False
    return str(chat_id) == str(community_group_id)
