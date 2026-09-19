import time
import logging
from typing import List, Optional, Tuple
from aiogram import Router, Bot
from aiogram.types import Message, ChatPermissions
from aiogram.filters import Command, CommandObject
from bot.admin_check import is_group_admin, invalidate_admin_cache
from bot.group_scope import is_community_group_chat
from bot.api_client import BackendClient
from bot.language import get_active_language
from app.i18n import t
from app.telegram_text import escape_telegram_markdown

logger = logging.getLogger(__name__)
moderation_router = Router()

MUTED_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)
UNMUTED_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)


def _resolve_target(message: Message, command: CommandObject) -> Tuple[Optional[int], Optional[str], List[str]]:
    """
    Who a moderation command targets: the author of the replied-to message, or a numeric Telegram
    user id given as the first argument.

    Returns `(user_id, display_name, rest_args)`; `rest_args` are the remaining arguments (a mute
    duration, a warn reason). `(None, None, [])` when there is no target.
    """
    args = (command.args or "").split()

    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        display_name = target.username or target.first_name or f"User_{target.id}"
        return target.id, display_name, args

    if args and args[0].lstrip("-").isdigit():
        return int(args[0]), f"User_{args[0]}", args[1:]

    return None, None, []


async def _check_admin(message: Message, bot: Bot, lang: str) -> bool:
    """Check the sender is a group admin (live, via Telegram); reply with a refusal if not."""
    if not await is_group_admin(bot, message.chat.id, message.from_user.id):
        await message.reply(t("moderation_not_admin", lang))
        return False
    return True


async def _moderation_target(
    message: Message, command: CommandObject, bot: Bot, backend_client: Optional[BackendClient]
) -> Optional[Tuple[str, int, str, List[str]]]:
    """
    What every moderation command needs before acting: `(lang, user_id, display_name, rest_args)`.

    None when the command must not run: outside the community group (ignored silently), sent by someone
    who is not a group admin, or with no member to act on (both answered with a message).
    """
    if not await is_community_group_chat(message.chat.id, backend_client=backend_client):
        return None
    lang = await get_active_language(backend_client=backend_client)
    if not await _check_admin(message, bot, lang):
        return None

    user_id, display_name, rest = _resolve_target(message, command)
    if user_id is None:
        await message.reply(t("moderation_no_target", lang), parse_mode="Markdown")
        return None
    return lang, user_id, display_name, rest


@moderation_router.message(Command("mute"))
async def handle_mute(
    message: Message,
    command: CommandObject,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """`/mute [seconds]` (reply or user id): stop a member from writing, for a duration or until unmuted."""
    target = await _moderation_target(message, command, bot, backend_client)
    if target is None:
        return
    lang, user_id, display_name, rest = target

    duration_seconds: Optional[int] = None
    if rest:
        try:
            duration_seconds = int(rest[0])
        except ValueError:
            duration_seconds = None

    until_date = None
    if duration_seconds and duration_seconds > 0:
        until_date = int(time.time()) + duration_seconds

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user_id,
            permissions=MUTED_PERMISSIONS,
            until_date=until_date,
        )
    except Exception as exc:
        logger.error("Failed to mute user %s in chat %s: %s", user_id, message.chat.id, exc)
        await message.reply(t("moderation_mute_error", lang))
        return

    safe_name = escape_telegram_markdown(display_name)
    duration_text = (
        t("moderation_mute_duration_seconds", lang, seconds=duration_seconds)
        if duration_seconds
        else t("moderation_mute_indefinite", lang)
    )
    await message.reply(t("moderation_mute_success", lang, name=safe_name, duration_text=duration_text), parse_mode="Markdown")


@moderation_router.message(Command("unmute"))
async def handle_unmute(
    message: Message,
    command: CommandObject,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """`/unmute` (reply or user id): give a muted member their permissions back."""
    target = await _moderation_target(message, command, bot, backend_client)
    if target is None:
        return
    lang, user_id, display_name, _ = target

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user_id,
            permissions=UNMUTED_PERMISSIONS,
        )
    except Exception as exc:
        logger.error("Failed to unmute user %s in chat %s: %s", user_id, message.chat.id, exc)
        await message.reply(t("moderation_unmute_error", lang))
        return

    safe_name = escape_telegram_markdown(display_name)
    await message.reply(t("moderation_unmute_success", lang, name=safe_name), parse_mode="Markdown")


@moderation_router.message(Command("ban"))
async def handle_ban(
    message: Message,
    command: CommandObject,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """`/ban` (reply or user id): remove a member and stop them from rejoining."""
    target = await _moderation_target(message, command, bot, backend_client)
    if target is None:
        return
    lang, user_id, display_name, _ = target

    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=user_id)
    except Exception as exc:
        logger.error("Failed to ban user %s in chat %s: %s", user_id, message.chat.id, exc)
        await message.reply(t("moderation_ban_error", lang))
        return

    safe_name = escape_telegram_markdown(display_name)
    await message.reply(t("moderation_ban_success", lang, name=safe_name), parse_mode="Markdown")


@moderation_router.message(Command("kick"))
async def handle_kick(
    message: Message,
    command: CommandObject,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """`/kick` (reply or user id): remove a member who may rejoin later."""
    target = await _moderation_target(message, command, bot, backend_client)
    if target is None:
        return
    lang, user_id, display_name, _ = target

    try:
        # Telegram's documented "kick" idiom: ban then immediately unban, so
        # the member is removed but is still allowed to rejoin (unlike /ban).
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=user_id)
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=user_id, only_if_banned=True)
    except Exception as exc:
        logger.error("Failed to kick user %s in chat %s: %s", user_id, message.chat.id, exc)
        await message.reply(t("moderation_kick_error", lang))
        return

    safe_name = escape_telegram_markdown(display_name)
    await message.reply(t("moderation_kick_success", lang, name=safe_name), parse_mode="Markdown")


@moderation_router.message(Command("warn"))
async def handle_warn(
    message: Message,
    command: CommandObject,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """`/warn [reason]` (reply or user id): record a warning and report the member's total."""
    target = await _moderation_target(message, command, bot, backend_client)
    if target is None:
        return
    lang, user_id, display_name, rest = target

    reason = " ".join(rest).strip() or None
    warned_by = message.from_user.username or message.from_user.first_name or f"Admin_{message.from_user.id}"

    client = backend_client or BackendClient()
    try:
        await client.create_warning(
            user_id=user_id,
            group_id=message.chat.id,
            warned_by=warned_by,
            reason=reason,
        )
        warnings_data = await client.list_warnings(user_id=user_id, group_id=message.chat.id)
        total = warnings_data.get("count", "?")
    except Exception as exc:
        logger.error("Failed to record warning for user %s in chat %s: %s", user_id, message.chat.id, exc)
        await message.reply(t("moderation_warn_error", lang))
        return

    safe_name = escape_telegram_markdown(display_name)
    reason_text = f" ({escape_telegram_markdown(reason)})" if reason else ""
    await message.reply(
        t("moderation_warn_success", lang, name=safe_name, reason_text=reason_text, total=total),
        parse_mode="Markdown",
    )
