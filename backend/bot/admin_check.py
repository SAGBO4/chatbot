import time
import logging
from typing import Dict, Tuple, Optional
from aiogram import Bot

logger = logging.getLogger(__name__)

ADMIN_STATUSES = {"administrator", "creator"}
_CACHE_TTL_SECONDS = 15.0

# In-memory cache of recent admin-check results, keyed by (chat_id, user_id).
# Short TTL (15s) guarantees fast reaction when an admin is demoted or leaves,
# while still dampening burst moderation actions.
_admin_status_cache: Dict[Tuple[int, int], Tuple[bool, float]] = {}


def invalidate_admin_cache(chat_id: Optional[int] = None, user_id: Optional[int] = None) -> None:
    """Evicts cached admin status for a specific user/chat or all entries."""
    if chat_id is None and user_id is None:
        _admin_status_cache.clear()
        return

    to_remove = [
        k for k in _admin_status_cache
        if (chat_id is None or k[0] == chat_id) and (user_id is None or k[1] == user_id)
    ]
    for k in to_remove:
        _admin_status_cache.pop(k, None)


async def is_group_admin(bot: Bot, chat_id: int, user_id: int, force_refresh: bool = False) -> bool:
    """
    Verifies, via the Telegram Bot API, whether user_id currently holds an
    administrator or creator role in chat_id.

    Telegram is the single source of truth for group roles, so this always
    re-verifies live rather than trusting a local allowlist - results are
    only cached for a short TTL (15s) to avoid hammering the API when an admin
    issues several moderation commands in a row, with instant eviction on permission errors.
    """
    cache_key = (chat_id, user_id)
    now = time.time()
    if not force_refresh:
        cached = _admin_status_cache.get(cache_key)
        if cached is not None and (now - cached[1]) < _CACHE_TTL_SECONDS:
            return cached[0]

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        result = member.status in ADMIN_STATUSES
    except Exception as exc:
        logger.warning(
            "Failed to verify admin status for user %s in chat %s: %s", user_id, chat_id, exc
        )
        result = False

    _admin_status_cache[cache_key] = (result, now)
    return result
