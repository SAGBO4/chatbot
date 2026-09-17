import time
import logging
from typing import Optional, Tuple, Union
from bot.api_client import BackendClient

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30.0

# In-memory cache of the persisted community group id, refreshed on a short
# TTL. Mirrors bot/admin_check.py and bot/access_control.py's pattern:
# invalidate_community_group_cache() is called right after a successful
# /setup_community so the same process picks up the change immediately,
# without waiting out the TTL (design.md decision 3).
_cached_community_group_id: Optional[Tuple[Optional[int], float]] = None


def invalidate_community_group_cache() -> None:
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
    Returns True only if chat_id matches the currently configured community
    group (resolved dynamically per community-group-setup - see
    get_community_group_id - not a fixed environment value). Returns False
    when no community group is configured yet, so an unconfigured deployment
    can never accidentally match.
    """
    community_group_id = await get_community_group_id(backend_client=backend_client)
    if community_group_id is None:
        return False
    return str(chat_id) == str(community_group_id)
