import time
import asyncio
import logging
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Set
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from app.config import settings
from bot.keyboards import get_community_resolution_keyboard
from bot.api_client import BackendClient
from bot.admin_check import is_bot_admin
from bot.group_scope import is_community_group_chat as _is_community_group_chat
from bot.ticket_escalation import create_ticket_and_notify_admin_group
from bot.language import get_active_language
from bot.messaging import call_with_markdown_fallback
from app.i18n import t
from app.telegram_text import (
    escape_telegram_markdown,
    truncate_telegram_text,
    TELEGRAM_MAX_MESSAGE_LENGTH,
    EDITED_MESSAGE_BASE_LENGTH,
)

logger = logging.getLogger(__name__)
community_router = Router()

DEFAULT_PURGE_COUNT = 5
MAX_PURGE_COUNT = 50

# Ids of the last 200 /ask answers posted per community group, so /purge can delete them without a
# database. Lost on restart: the worst case is that /purge finds nothing to delete.
_recent_bot_messages: Dict[int, Deque[int]] = defaultdict(lambda: deque(maxlen=200))

# asyncio keeps only weak references to tasks, so an unreferenced expiry task could be garbage-collected
# while it sleeps and its buttons would never expire.
_background_tasks: Set[asyncio.Task] = set()


def _track_bot_message(chat_id: int, message_id: int) -> None:
    """Remember a bot message so /purge can delete it later."""
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
    Remove an answer's YES/NO buttons once the timeout has passed, unless it was resolved, escalated
    or replaced by a newer question meanwhile (the state no longer holds the same timestamp).
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
    """Wait for the timeout, then expire the buttons."""
    await asyncio.sleep(settings.COMMUNITY_RESOLUTION_TIMEOUT_SECONDS)
    await _expire_resolution_buttons(bot, state, chat_id, message_id, timestamp)


def _is_answer_expired(timestamp: Optional[float]) -> bool:
    """Whether an answer is older than COMMUNITY_RESOLUTION_TIMEOUT_SECONDS (a missing timestamp counts as expired)."""
    if timestamp is None:
        return True
    return (time.time() - timestamp) > settings.COMMUNITY_RESOLUTION_TIMEOUT_SECONDS


async def _pending_answer(callback: CallbackQuery, state: FSMContext, lang: str) -> Optional[dict]:
    """
    The stored question and answer that a YES / NO click refers to, or None after telling the user why not.

    None when the answer was already handled (a double click, or another admin got there first), or when the
    buttons outlived COMMUNITY_RESOLUTION_TIMEOUT_SECONDS (they are removed, and the state cleared).
    """
    user_data = await state.get_data()
    if not user_data.get("last_question"):
        await callback.answer(t("ticket_already_handled", lang), show_alert=False)
        return None

    if _is_answer_expired(user_data.get("last_answer_timestamp")):
        await state.clear()
        await callback.answer(t("community_resolution_expired", lang), show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as exc:
            logger.warning("Failed to clear the expired keyboard: %s", exc)
        return None
    return user_data


async def _answer_community_question(
    message: Message,
    question: str,
    state: FSMContext,
    bot: Bot,
    client: BackendClient,
    lang: str,
    photo_file_id: Optional[str] = None,
) -> None:
    """
    Answer `question` directly in the community group (never by DM), tagging the asker, through the
    same knowledge-base pipeline as a private chat: query, post the answer with the YES/NO keyboard,
    track it for /purge, and schedule the buttons' expiry.

    `photo_file_id`: when the question came with a screenshot, its Telegram file id - remembered so a
    later NO can forward the actual image to the support group (never run through OCR or a vision model).
    """
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
    reply_text = truncate_telegram_text(reply_text, max_length=TELEGRAM_MAX_MESSAGE_LENGTH, suffix=t("truncated_suffix", lang))
    sent = await call_with_markdown_fallback(
        message.answer, reply_text, reply_markup=get_community_resolution_keyboard(lang), what="Community answer"
    )

    _track_bot_message(message.chat.id, sent.message_id)

    timestamp = time.time()
    await state.update_data(
        last_question=question,
        last_answer=answer,
        last_answer_timestamp=timestamp,
        last_answer_message_id=sent.message_id,
        asking_user_handle=user_handle,
        last_photo_file_id=photo_file_id,
    )
    task = asyncio.create_task(_schedule_expiry(bot, state, message.chat.id, sent.message_id, timestamp))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@community_router.message(Command("ask"))
async def handle_community_ask(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """`/ask <question>` in the community group: answer publicly through the same pipeline as private chats, tagging the asker."""
    if not await _is_community_group_chat(message.chat.id, backend_client=backend_client):
        return

    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)

    question = (command.args or "").strip()
    if not question:
        await message.reply(t("community_ask_usage", lang), parse_mode="Markdown")
        return

    await _answer_community_question(message, question, state, bot, client, lang)


@community_router.message(F.chat.type.in_({"group", "supergroup"}), F.text, ~F.text.startswith("/"))
async def handle_community_plain_question(
    message: Message,
    state: FSMContext,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """
    A plain-text question typed directly in the community group (no `/ask`): answered in the group
    itself, exactly like `/ask`, instead of silently going unanswered.
    """
    if not await _is_community_group_chat(message.chat.id, backend_client=backend_client):
        return

    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)

    question = (message.text or "").strip()
    if not question:
        return
    if len(question) > TELEGRAM_MAX_MESSAGE_LENGTH:
        await message.reply(t("question_too_long", lang, max_length=TELEGRAM_MAX_MESSAGE_LENGTH))
        return

    await _answer_community_question(message, question, state, bot, client, lang)


@community_router.message(F.chat.type.in_({"group", "supergroup"}), F.photo)
async def handle_community_photo_question(
    message: Message,
    state: FSMContext,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """
    A screenshot posted directly in the community group: answered like a plain-text question, using
    its caption (or a placeholder when there is none). On NO, the image itself is forwarded to the
    support group so an agent can look at it - never run through OCR or a vision model.
    """
    if not await _is_community_group_chat(message.chat.id, backend_client=backend_client):
        return

    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)

    caption = (message.caption or "").strip()
    if len(caption) > TELEGRAM_MAX_MESSAGE_LENGTH:
        await message.reply(t("question_too_long", lang, max_length=TELEGRAM_MAX_MESSAGE_LENGTH))
        return
    question = caption or t("photo_no_caption_question", lang)
    photo_file_id = message.photo[-1].file_id

    await _answer_community_question(message, question, state, bot, client, lang, photo_file_id=photo_file_id)


@community_router.callback_query(F.data == "cresolve:yes")
async def handle_community_resolve_yes(
    callback: CallbackQuery, state: FSMContext, backend_client: Optional[BackendClient] = None
):
    """YES on a community answer: mark it resolved (or say it expired)."""
    lang = await get_active_language(backend_client=backend_client)
    if await _pending_answer(callback, state, lang) is None:
        return

    await state.clear()
    await callback.answer(t("resolve_yes_ack", lang))
    base_text = truncate_telegram_text(callback.message.text or "", max_length=EDITED_MESSAGE_BASE_LENGTH, suffix=t("truncated_suffix", lang))
    resolved_notice = t("community_resolved_notice", lang, base_text=base_text)
    await call_with_markdown_fallback(
        callback.message.edit_text, resolved_notice, reply_markup=None,
        what="Edit of the community resolved notice", swallow_failure=True,
    )


@community_router.callback_query(F.data == "cresolve:no")
async def handle_community_resolve_no(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """
    NO on a community answer: open a ticket like the private flow does.

    The community message only gets a neutral acknowledgement; the ticket card, question and answer
    go to the admin/support group only.
    """
    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)
    user_data = await _pending_answer(callback, state, lang)
    if user_data is None:
        return
    last_question = user_data["last_question"]

    await state.clear()
    last_answer = user_data.get("last_answer", t("no_answer", lang))
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
            lang=lang,
            photo_file_id=user_data.get("last_photo_file_id"),
        )
        ticket_id = ticket["id"]
        await callback.answer(t("ticket_created_ack", lang))

        base_text = callback.message.text or ""
        if len(base_text) > EDITED_MESSAGE_BASE_LENGTH:
            base_text = base_text[:EDITED_MESSAGE_BASE_LENGTH] + t("truncated_suffix", lang)
        ack_text = t("community_ticket_ack", lang, base_text=base_text)
        await call_with_markdown_fallback(
            callback.message.edit_text, ack_text, reply_markup=None,
            what="Edit of the community ticket notice", swallow_failure=True,
        )
        logger.info("Community ticket #%s created for user %s", ticket_id, user_id)
    except Exception as exc:
        logger.error("Error creating or escalating community ticket: %s", exc)
        await callback.answer(t("ticket_creation_error", lang), show_alert=True)


def _parse_purge_count(text: str) -> int:
    """Number after `/purge`, clamped to 1..MAX_PURGE_COUNT; DEFAULT_PURGE_COUNT if missing or not a number."""
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
    Admin only: delete up to N of the bot's latest `/ask` answers in the community group
    (default DEFAULT_PURGE_COUNT, at most MAX_PURGE_COUNT).

    Only answers tracked by `_track_bot_message` can be deleted, i.e. `/ask` answers; other bot
    messages (moderation or crypto replies) are not tracked.
    """
    if not await _is_community_group_chat(message.chat.id, backend_client=backend_client):
        return

    lang = await get_active_language(backend_client=backend_client)

    if not await is_bot_admin(bot, message.chat.id, message.from_user.id, backend_client=backend_client):
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
