import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.keyboards import get_resolution_keyboard, get_webapp_keyboard
from bot.access_control import is_authorized, is_owner
from bot.admin_check import is_bot_admin
from bot.api_client import BackendClient
from bot.group_scope import is_community_group_chat
from bot.ticket_escalation import create_ticket_and_notify_admin_group
from bot.language import get_active_language
from bot.messaging import call_with_markdown_fallback
from app.i18n import t
from app.telegram_text import truncate_telegram_text, TELEGRAM_MAX_MESSAGE_LENGTH, EDITED_MESSAGE_BASE_LENGTH
from app.config import settings

logger = logging.getLogger(__name__)
user_router = Router()


class UserQueryState(StatesGroup):
    """Set once the bot has answered, while it waits for the user's YES / NO."""

    waiting_for_resolution = State()


@user_router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, backend_client: Optional[BackendClient] = None):
    """/start: welcome message, with the WebApp button when TELEGRAM_WEBAPP_URL is set."""
    await state.clear()
    lang = await get_active_language(backend_client=backend_client)
    url = settings.TELEGRAM_WEBAPP_URL
    keyboard = get_webapp_keyboard(url, lang=lang) if url else None
    await message.answer(t("welcome", lang), parse_mode="Markdown", reply_markup=keyboard)


@user_router.message(Command("webapp", "app"))
async def handle_webapp(message: Message, backend_client: Optional[BackendClient] = None):
    """/webapp: a button that opens the Mini App."""
    lang = await get_active_language(backend_client=backend_client)
    chat = getattr(message, "chat", None)
    is_group = bool(chat and getattr(chat, "type", None) in ("group", "supergroup"))
    if is_group:
        await message.answer(t("webapp_group_redirect", lang))
        return

    url = settings.TELEGRAM_WEBAPP_URL
    if not url:
        await message.answer(t("webapp_not_configured", lang))
        return

    await message.answer(
        t("webapp_prompt", lang),
        reply_markup=get_webapp_keyboard(url, text=t("button_open_webapp", lang), lang=lang, is_group=False),
    )


@user_router.message(Command("help", "list"))
async def handle_help(message: Message, bot: Bot, backend_client: Optional[BackendClient] = None):
    """/help, /list: how to use the bot, plus every command the sender may run given their role and chat."""
    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)
    user_id = message.from_user.id
    is_group_chat = message.chat.type in ("group", "supergroup")

    url = settings.TELEGRAM_WEBAPP_URL
    sections = []

    if is_group_chat:
        sections.append(t("help_group_intro", lang))
        sections.append(t("help_group_member_commands", lang))
        sections.append(t("help_crypto_commands", lang))

        if await is_bot_admin(bot, message.chat.id, user_id, backend_client=client):
            sections.append(t("help_admin_commands", lang))
            sections.append(t("help_setup_commands", lang))
            if is_owner(user_id):
                sections.append(t("help_owner_commands", lang))
    else:
        sections.append(t("help_intro", lang))
        sections.append(t("help_general_commands", lang))
        if url:
            sections.append(t("help_webapp_command", lang))
        sections.append(t("help_crypto_commands", lang))

        if await is_authorized(user_id, backend_client=client):
            sections.append(t("help_setup_commands", lang))
            if is_owner(user_id):
                sections.append(t("help_owner_commands", lang))

    keyboard = None if is_group_chat else (get_webapp_keyboard(url, lang=lang, is_group=False) if url else None)
    await call_with_markdown_fallback(
        message.answer,
        "".join(sections),
        reply_markup=keyboard,
        what="Help/list command",
    )



async def _answer_private_question(
    message: Message,
    question: str,
    state: FSMContext,
    client: BackendClient,
    lang: str,
    photo_file_id: Optional[str] = None,
) -> None:
    """
    Answer `question` in the private chat, from the knowledge base, then ask whether it solved the
    problem. Shared by a typed question and a screenshot (its caption, or a placeholder when none):
    `photo_file_id` is remembered so a later NO can forward the actual image to the support group.
    """
    user_id = message.from_user.id
    user_handle = message.from_user.username or message.from_user.first_name

    try:
        data = await client.query(query=question, user_id=user_id, user_handle=user_handle)
        answer = data.get("answer", "")

        # Remembered so that clicking NO can open a ticket with this question and answer
        await state.update_data(
            last_question=question,
            last_answer=answer,
            last_photo_file_id=photo_file_id,
        )

        reply_text = t("answer_prompt", lang, answer=answer)
        reply_text = truncate_telegram_text(reply_text, max_length=TELEGRAM_MAX_MESSAGE_LENGTH, suffix=t("truncated_suffix", lang))
        await call_with_markdown_fallback(
            message.answer, reply_text, reply_markup=get_resolution_keyboard(lang=lang), what="Answer"
        )
        await state.set_state(UserQueryState.waiting_for_resolution)

    except Exception as exc:
        logger.error("Error querying backend: %s", exc)
        await message.answer(t("query_backend_error", lang))


@user_router.message(F.chat.type == "private", Command("ask"))
async def handle_user_ask(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    backend_client: Optional[BackendClient] = None,
):
    """
    /ask in private chat: answer from the knowledge base, supporting:
    - /ask <question>
    - photo message with caption /ask [<question>]
    - reply to a photo with /ask [<question>]
    """
    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)

    photo = getattr(message, "photo", None)
    reply_to = getattr(message, "reply_to_message", None)
    reply_photo = getattr(reply_to, "photo", None) if reply_to else None

    photo_file_id: Optional[str] = None
    if photo:
        photo_file_id = photo[-1].file_id
    elif reply_photo:
        photo_file_id = reply_photo[-1].file_id

    question = (command.args or "").strip()
    if not question:
        if reply_photo:
            caption = (getattr(reply_to, "caption", None) or "").strip()
            question = caption if caption else t("photo_no_caption_question", lang)
        elif photo:
            question = t("photo_no_caption_question", lang)

    if not question:
        await message.answer(t("community_ask_usage", lang), parse_mode="Markdown")
        return

    if len(question) > TELEGRAM_MAX_MESSAGE_LENGTH:
        await message.answer(t("question_too_long", lang, max_length=TELEGRAM_MAX_MESSAGE_LENGTH))
        return

    await _answer_private_question(message, question, state, client, lang, photo_file_id=photo_file_id)


@user_router.message(F.chat.type == "private", F.text)
async def handle_user_query(
    message: Message,
    state: FSMContext,
    backend_client: Optional[BackendClient] = None,
):
    """Answer a private-chat question from the knowledge base, then ask whether it solved the problem."""
    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)
    user_query = message.text.strip()
    if len(user_query) > TELEGRAM_MAX_MESSAGE_LENGTH:
        await message.answer(t("question_too_long", lang, max_length=TELEGRAM_MAX_MESSAGE_LENGTH))
        return

    reply_to = getattr(message, "reply_to_message", None)
    reply_photo = getattr(reply_to, "photo", None) if reply_to else None
    photo_file_id = reply_photo[-1].file_id if reply_photo else None

    await _answer_private_question(message, user_query, state, client, lang, photo_file_id=photo_file_id)


@user_router.message(F.chat.type == "private", F.photo)
async def handle_user_photo_query(
    message: Message,
    state: FSMContext,
    backend_client: Optional[BackendClient] = None,
):
    """
    A screenshot sent directly in the private chat: answered like a typed question, using its caption
    (or a placeholder when there is none - the screenshot alone can be enough). Never run through OCR
    or a vision model; on NO, the image itself is forwarded to the support group so an agent can look
    at it (see create_ticket_and_notify_admin_group).
    """
    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)
    caption = (message.caption or "").strip()
    if len(caption) > TELEGRAM_MAX_MESSAGE_LENGTH:
        await message.answer(t("question_too_long", lang, max_length=TELEGRAM_MAX_MESSAGE_LENGTH))
        return
    question = caption or t("photo_no_caption_question", lang)
    photo_file_id = message.photo[-1].file_id

    await _answer_private_question(message, question, state, client, lang, photo_file_id=photo_file_id)


@user_router.callback_query(F.data.startswith("resolve:yes"))
async def handle_resolve_yes(
    callback: CallbackQuery, state: FSMContext, backend_client: Optional[BackendClient] = None
):
    """YES: mark the answer as resolved and remove the buttons."""
    await state.clear()
    lang = await get_active_language(backend_client=backend_client)
    await callback.answer(t("resolve_yes_ack", lang))
    base_text = truncate_telegram_text(callback.message.text or "", max_length=EDITED_MESSAGE_BASE_LENGTH, suffix=t("truncated_suffix", lang))
    resolved_notice = t("resolved_notice", lang, base_text=base_text)
    await call_with_markdown_fallback(
        callback.message.edit_text, resolved_notice, reply_markup=None,
        what="Edit of the resolved notice", swallow_failure=True,
    )


@user_router.callback_query(F.data.startswith("resolve:no"))
async def handle_resolve_no(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """NO: open a ticket, post its card to the support group and tell the user."""
    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)
    user_data = await state.get_data()
    last_question = user_data.get("last_question")
    if not last_question:
        await callback.answer(t("ticket_already_handled", lang), show_alert=False)
        return

    # Clear context upfront to prevent concurrent double-click ticket creation
    await state.clear()
    last_answer = user_data.get("last_answer", t("no_answer", lang))

    user_id = callback.from_user.id
    user_handle = callback.from_user.username or callback.from_user.first_name or f"User_{user_id}"

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

        # Editing the message can fail (Markdown, deleted message); the ticket is already created by now
        base_text = callback.message.text or ""
        if len(base_text) > EDITED_MESSAGE_BASE_LENGTH:
            base_text = base_text[:EDITED_MESSAGE_BASE_LENGTH] + t("truncated_suffix", lang)
        confirmation_text = t("ticket_escalated_notice", lang, base_text=base_text, ticket_id=ticket_id)
        await call_with_markdown_fallback(
            callback.message.edit_text, confirmation_text, reply_markup=None,
            what="Edit of the escalation notice", swallow_failure=True,
        )
    except Exception as exc:
        logger.error("Error creating or escalating ticket: %s", exc)
        await callback.answer(t("ticket_creation_error", lang), show_alert=True)
