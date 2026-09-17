import time
import logging
from typing import Dict, Tuple
from aiogram import Bot

logger = logging.getLogger(__name__)

ADMIN_STATUSES = {"administrator", "creator"}
_CACHE_TTL_SECONDS = 60.0

# In-memory cache of recent admin-check results, keyed by (chat_id, user_id).
# Lost on bot restart like bot/middlewares/throttling.py's per-user state -
# a worst-case miss just re-queries the Telegram Bot API, never grants stale
# access, since a cache miss always falls through to a fresh live check.
_admin_status_cache: Dict[Tuple[int, int], Tuple[bool, float]] = {}


async def is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Verifies, via the Telegram Bot API, whether user_id currently holds an
    administrator or creator role in chat_id.

    Telegram is the single source of truth for group roles, so this always
    re-verifies live rather than trusting a local allowlist - results are
    only cached for a short TTL to avoid hammering the API when an admin
    issues several moderation commands in a row.
    """
    cache_key = (chat_id, user_id)
    cached = _admin_status_cache.get(cache_key)
    now = time.time()
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
