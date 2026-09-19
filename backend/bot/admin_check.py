import logging
from typing import Optional
from aiogram import Bot
from bot.ttl_cache import MISSING, TTLCache

logger = logging.getLogger(__name__)

ADMIN_STATUSES = {"administrator", "creator"}

# Recent admin-check results, keyed by (chat_id, user_id). The short TTL (15s) keeps the reaction fast when
# an admin is demoted or leaves, while still dampening bursts of moderation commands.
_admin_status_cache = TTLCache(15.0)


def invalidate_admin_cache(chat_id: Optional[int] = None, user_id: Optional[int] = None) -> None:
    """Evicts cached admin status for a specific user/chat or all entries."""
    _admin_status_cache.discard_where(
        lambda key: (chat_id is None or key[0] == chat_id) and (user_id is None or key[1] == user_id)
    )


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
    if not force_refresh:
        cached = _admin_status_cache.get(cache_key)
        if cached is not MISSING:
            return cached

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        result = member.status in ADMIN_STATUSES
    except Exception as exc:
        logger.warning(
            "Failed to verify admin status for user %s in chat %s: %s", user_id, chat_id, exc
        )
        result = False

    _admin_status_cache.set(cache_key, result)
    return result
