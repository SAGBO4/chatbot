import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.keyboards import get_resolution_keyboard, get_webapp_keyboard
from bot.api_client import BackendClient
from bot.ticket_escalation import create_ticket_and_notify_admin_group
from bot.language import get_active_language
from app.i18n import t
from app.telegram_text import truncate_telegram_text, TELEGRAM_MAX_MESSAGE_LENGTH
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
    url = settings.TELEGRAM_WEBAPP_URL
    if not url:
        await message.answer(t("webapp_not_configured", lang))
        return
    await message.answer(
        t("webapp_prompt", lang),
        reply_markup=get_webapp_keyboard(url, text=t("button_open_webapp", lang)),
    )


@user_router.message(Command("help"))
async def handle_help(message: Message, backend_client: Optional[BackendClient] = None):
    """/help: how to use the bot."""
    lang = await get_active_language(backend_client=backend_client)
    url = settings.TELEGRAM_WEBAPP_URL
    keyboard = get_webapp_keyboard(url, lang=lang) if url else None
    await message.answer(t("help", lang), parse_mode="Markdown", reply_markup=keyboard)


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

    user_id = message.from_user.id
    user_handle = message.from_user.username or message.from_user.first_name

    try:
        data = await client.query(query=user_query, user_id=user_id, user_handle=user_handle)
        answer = data.get("answer", "")

        # Remembered so that clicking NO can open a ticket with this question and answer
        await state.update_data(
            last_question=user_query,
            last_answer=answer,
        )

        reply_text = t("answer_prompt", lang, answer=answer)
        reply_text = truncate_telegram_text(reply_text, max_length=4000, suffix=t("truncated_suffix", lang))
        try:
            await message.answer(reply_text, reply_markup=get_resolution_keyboard(lang=lang), parse_mode="Markdown")
        except Exception as send_err:
            logger.warning("Failed to send answer in markdown, falling back to plain text: %s", send_err)
            await message.answer(reply_text, reply_markup=get_resolution_keyboard(lang=lang))
        await state.set_state(UserQueryState.waiting_for_resolution)

    except Exception as exc:
        logger.error("Error querying backend: %s", exc)
        await message.answer(t("query_backend_error", lang))


@user_router.callback_query(F.data.startswith("resolve:yes"))
async def handle_resolve_yes(
    callback: CallbackQuery, state: FSMContext, backend_client: Optional[BackendClient] = None
):
    """YES: mark the answer as resolved and remove the buttons."""
    await state.clear()
    lang = await get_active_language(backend_client=backend_client)
    await callback.answer(t("resolve_yes_ack", lang))
    base_text = truncate_telegram_text(callback.message.text or "", max_length=3700, suffix=t("truncated_suffix", lang))
    resolved_notice = t("resolved_notice", lang, base_text=base_text)
    try:
        await callback.message.edit_text(
            resolved_notice,
            reply_markup=None,
            parse_mode="Markdown",
        )
    except Exception as edit_err:
        logger.warning("Markdown edit_text failed in resolve_yes, falling back to plain text: %s", edit_err)
        try:
            await callback.message.edit_text(resolved_notice, reply_markup=None)
        except Exception as e:
            logger.warning("Failed to edit user message in resolve_yes: %s", e)


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
        )
        ticket_id = ticket["id"]

        await callback.answer(t("ticket_created_ack", lang))

        # Editing the message can fail (Markdown, deleted message); the ticket is already created by now
        base_text = callback.message.text or ""
        if len(base_text) > 3700:
            base_text = base_text[:3700] + t("truncated_suffix", lang)
        confirmation_text = t("ticket_escalated_notice", lang, base_text=base_text, ticket_id=ticket_id)
        try:
            await callback.message.edit_text(
                confirmation_text,
                reply_markup=None,
                parse_mode="Markdown",
            )
        except Exception as edit_err:
            logger.warning("Markdown edit_text failed in resolve_no, retrying in plain text: %s", edit_err)
            try:
                await callback.message.edit_text(confirmation_text, reply_markup=None)
            except Exception as e:
                logger.warning("Failed to edit user message in resolve_no: %s", e)
    except Exception as exc:
        logger.error("Error creating or escalating ticket: %s", exc)
        await callback.answer(t("ticket_creation_error", lang), show_alert=True)
