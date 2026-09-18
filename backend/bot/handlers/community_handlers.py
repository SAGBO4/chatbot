import time
import asyncio
import logging
from collections import defaultdict, deque
from typing import Deque, Dict, Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from app.config import settings
from bot.keyboards import get_community_resolution_keyboard
from bot.api_client import BackendClient
from bot.admin_check import is_group_admin
from bot.group_scope import is_community_group_chat as _is_community_group_chat
from bot.ticket_escalation import create_ticket_and_notify_admin_group
from bot.language import get_active_language
from bot.i18n import t
from bot.utils import escape_telegram_markdown, truncate_telegram_text

logger = logging.getLogger(__name__)
community_router = Router()

DEFAULT_PURGE_COUNT = 5
MAX_PURGE_COUNT = 50

# Bounded in-memory record of message ids the bot has posted in each
# community group, so /purge can delete recent bot messages without a
# persistent store. Lost on restart, same trade-off as the throttling
# middleware's in-memory state - worst case /purge finds nothing to delete.
_recent_bot_messages: Dict[int, Deque[int]] = defaultdict(lambda: deque(maxlen=200))


def _track_bot_message(chat_id: int, message_id: int) -> None:
    _recent_bot_messages[chat_id].append(message_id)


def _build_mention(user, lang: str = "fr") -> str:
    """Builds a Telegram-Markdown mention that notifies the asking member."""
    if user.username:
        return f"@{escape_telegram_markdown(user.username)}"
    display_name = user.first_name or t("community_mention_fallback", lang, user_id=user.id)
    return f"[{escape_telegram_markdown(display_name)}](tg://user?id={user.id})"


async def _expire_resolution_buttons(
    bot: Bot, state: FSMContext, chat_id: int, message_id: int, expected_timestamp: float
) -> None:
    """
    Disables a group-triggered answer's YES/NO keyboard once its inactivity
    timeout has elapsed, unless the answer was already resolved/escalated or
    superseded by a newer question in the meantime (state no longer carries
    the same timestamp).
    """
    data = await state.get_data()
    if data.get("last_answer_timestamp") != expected_timestamp:
        return
    await state.clear()
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
    except Exception as exc:
        logger.warning(
            "Failed to disable expired resolution buttons for message %s in chat %s: %s",
            message_id, chat_id, exc,
        )


async def _schedule_expiry(bot: Bot, state: FSMContext, chat_id: int, message_id: int, timestamp: float) -> None:
    await asyncio.sleep(settings.COMMUNITY_RESOLUTION_TIMEOUT_SECONDS)
    await _expire_resolution_buttons(bot, state, chat_id, message_id, timestamp)


def _is_answer_expired(timestamp: Optional[float]) -> bool:
    if timestamp is None:
        return True
    return (time.time() - timestamp) > settings.COMMUNITY_RESOLUTION_TIMEOUT_SECONDS


@community_router.message(Command("ask"))
async def handle_community_ask(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """
    Group-triggered question intake: `/ask <question>` in the configured
    Telegram Community Group is submitted to the same backend query pipeline
    as the private-DM flow, and answered publicly, tagging the asking member.
    """
    if not await _is_community_group_chat(message.chat.id, backend_client=backend_client):
        return

    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)

    question = (command.args or "").strip()
    if not question:
        await message.reply(t("community_ask_usage", lang), parse_mode="Markdown")
        return

    user_id = message.from_user.id
    user_handle = message.from_user.username or message.from_user.first_name or f"User_{user_id}"
    mention = _build_mention(message.from_user, lang)

    try:
        data = await client.query(query=question, user_id=user_id, user_handle=user_handle)
        answer = data.get("answer", "")
    except Exception as exc:
        logger.error("Error querying backend from community group: %s", exc)
        await message.reply(t("query_backend_error", lang))
        return

    reply_text = t("community_answer_prompt", lang, mention=mention, answer=answer)
    reply_text = truncate_telegram_text(reply_text, max_length=4000, suffix="...(tronqué)")
    try:
        sent = await message.answer(reply_text, reply_markup=get_community_resolution_keyboard(), parse_mode="Markdown")
    except Exception as send_err:
        logger.warning("Failed to send community answer in markdown, falling back to plain text: %s", send_err)
        sent = await message.answer(reply_text, reply_markup=get_community_resolution_keyboard())

    _track_bot_message(message.chat.id, sent.message_id)

    timestamp = time.time()
    await state.update_data(
        last_question=question,
        last_answer=answer,
        last_answer_timestamp=timestamp,
        last_answer_message_id=sent.message_id,
        asking_user_handle=user_handle,
    )
    asyncio.create_task(_schedule_expiry(bot, state, message.chat.id, sent.message_id, timestamp))


@community_router.callback_query(F.data == "cresolve:yes")
async def handle_community_resolve_yes(
    callback: CallbackQuery, state: FSMContext, backend_client: Optional[BackendClient] = None
):
    lang = await get_active_language(backend_client=backend_client)
    user_data = await state.get_data()
    last_question = user_data.get("last_question")
    if not last_question:
        await callback.answer(t("ticket_already_handled", lang), show_alert=False)
        return

    if _is_answer_expired(user_data.get("last_answer_timestamp")):
        await state.clear()
        await callback.answer(t("community_resolution_expired", lang), show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as exc:
            logger.warning("Failed to clear expired keyboard in community resolve_yes: %s", exc)
        return

    await state.clear()
    await callback.answer(t("resolve_yes_ack", lang))
    base_text = truncate_telegram_text(callback.message.text or "", max_length=3700, suffix="...(tronqué)")
    resolved_notice = t("community_resolved_notice", lang, base_text=base_text)
    try:
        await callback.message.edit_text(resolved_notice, reply_markup=None, parse_mode="Markdown")
    except Exception as edit_err:
        logger.warning("Markdown edit_text failed in community resolve_yes, falling back to plain text: %s", edit_err)
        try:
            await callback.message.edit_text(resolved_notice, reply_markup=None)
        except Exception as e:
            logger.warning("Failed to edit community message in resolve_yes: %s", e)


@community_router.callback_query(F.data == "cresolve:no")
async def handle_community_resolve_no(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """
    Escalates an unresolved group-triggered question to a ticket, exactly
    like the DM flow, but the community-group message is only ever updated
    with a neutral acknowledgement - the ticket card, question, and answer
    are posted solely to the admin/support group (create_ticket_and_notify_admin_group).
    """
    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)
    user_data = await state.get_data()
    last_question = user_data.get("last_question")
    if not last_question:
        await callback.answer(t("ticket_already_handled", lang), show_alert=False)
        return

    if _is_answer_expired(user_data.get("last_answer_timestamp")):
        await state.clear()
        await callback.answer(t("community_resolution_expired", lang), show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as exc:
            logger.warning("Failed to clear expired keyboard in community resolve_no: %s", exc)
        return

    await state.clear()
    last_answer = user_data.get("last_answer", "Aucune réponse")
    user_id = callback.from_user.id
    user_handle = user_data.get("asking_user_handle") or callback.from_user.username or f"User_{user_id}"

    try:
        ticket = await create_ticket_and_notify_admin_group(
            client=client,
            bot=bot,
            user_id=user_id,
            user_handle=user_handle,
            question=last_question,
            automated_answer=last_answer,
        )
        ticket_id = ticket["id"]
        await callback.answer(t("ticket_created_ack", lang))

        base_text = callback.message.text or ""
        if len(base_text) > 3700:
            base_text = base_text[:3700] + "...(tronqué)"
        ack_text = t("community_ticket_ack", lang, base_text=base_text)
        try:
            await callback.message.edit_text(ack_text, reply_markup=None, parse_mode="Markdown")
        except Exception as edit_err:
            logger.warning("Markdown edit_text failed in community resolve_no, retrying in plain text: %s", edit_err)
            try:
                await callback.message.edit_text(ack_text, reply_markup=None)
            except Exception as e:
                logger.warning("Failed to edit community message in resolve_no: %s", e)
        logger.info("Community ticket #%s created for user %s", ticket_id, user_id)
    except Exception as exc:
        logger.error("Error creating or escalating community ticket: %s", exc)
        await callback.answer(t("ticket_creation_error", lang), show_alert=True)


def _parse_purge_count(text: str) -> int:
    parts = (text or "").split()
    if len(parts) >= 2:
        try:
            count = int(parts[1])
            return max(1, min(count, MAX_PURGE_COUNT))
        except ValueError:
            pass
    return DEFAULT_PURGE_COUNT


@community_router.message(Command("purge"))
async def handle_purge(
    message: Message,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """
    Admin-only community-group cleanup: deletes up to N of the bot's most
    recent messages in the group (default DEFAULT_PURGE_COUNT, capped at
    MAX_PURGE_COUNT), so an admin can remove an unwanted bot reply without
    needing admin-group access.
    """
    if not await _is_community_group_chat(message.chat.id, backend_client=backend_client):
        return

    lang = await get_active_language(backend_client=backend_client)

    if not await is_group_admin(bot, message.chat.id, message.from_user.id):
        await message.reply(t("community_purge_not_admin", lang))
        return

    count = _parse_purge_count(message.text or "")
    queue = _recent_bot_messages.get(message.chat.id)
    deleted = 0
    if queue:
        to_delete = [queue.pop() for _ in range(min(count, len(queue)))]
        for message_id in to_delete:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=message_id)
                deleted += 1
            except Exception as exc:
                logger.warning("Failed to delete message %s during /purge: %s", message_id, exc)

    await message.reply(t("community_purge_result", lang, deleted=deleted))
