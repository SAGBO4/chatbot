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
from bot.i18n import t
from bot.utils import truncate_telegram_text, TELEGRAM_MAX_MESSAGE_LENGTH
from backend.config import settings

logger = logging.getLogger(__name__)
user_router = Router()


class UserQueryState(StatesGroup):
    waiting_for_resolution = State()


@user_router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, backend_client: Optional[BackendClient] = None):
    await state.clear()
    lang = await get_active_language(backend_client=backend_client)
    url = getattr(settings, "TELEGRAM_WEBAPP_URL", None)
    keyboard = get_webapp_keyboard(url) if url else None
    await message.answer(t("welcome", lang), parse_mode="Markdown", reply_markup=keyboard)


@user_router.message(Command("webapp", "app"))
async def handle_webapp(message: Message):
    url = getattr(settings, "TELEGRAM_WEBAPP_URL", None)
    if not url:
        await message.answer(
            "L'URL de la WebApp n'est pas encore configurée dans le fichier `.env` (variable `TELEGRAM_WEBAPP_URL`)."
        )
        return
    await message.answer(
        "Accédez au centre d'assistance officiel Stack Wallet :",
        reply_markup=get_webapp_keyboard(url, text="📱 Ouvrir l'Application Support"),
    )


@user_router.message(Command("help"))
async def handle_help(message: Message, backend_client: Optional[BackendClient] = None):
    lang = await get_active_language(backend_client=backend_client)
    url = getattr(settings, "TELEGRAM_WEBAPP_URL", None)
    keyboard = get_webapp_keyboard(url) if url else None
    await message.answer(t("help", lang), parse_mode="Markdown", reply_markup=keyboard)


@user_router.message(F.chat.type == "private", F.text)
async def handle_user_query(
    message: Message,
    state: FSMContext,
    backend_client: Optional[BackendClient] = None,
):
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

        # Save context in state for ticket creation if user clicks NON
        await state.update_data(
            last_question=user_query,
            last_answer=answer,
        )

        reply_text = t("answer_prompt", lang, answer=answer)
        reply_text = truncate_telegram_text(reply_text, max_length=4000, suffix="...(tronqué)")
        try:
            await message.answer(reply_text, reply_markup=get_resolution_keyboard(), parse_mode="Markdown")
        except Exception as send_err:
            logger.warning("Failed to send answer in markdown, falling back to plain text: %s", send_err)
            await message.answer(reply_text, reply_markup=get_resolution_keyboard())
        await state.set_state(UserQueryState.waiting_for_resolution)

    except Exception as exc:
        logger.error("Error querying backend: %s", exc)
        await message.answer(t("query_backend_error", lang))


@user_router.callback_query(F.data.startswith("resolve:yes"))
async def handle_resolve_yes(
    callback: CallbackQuery, state: FSMContext, backend_client: Optional[BackendClient] = None
):
    await state.clear()
    lang = await get_active_language(backend_client=backend_client)
    await callback.answer(t("resolve_yes_ack", lang))
    base_text = truncate_telegram_text(callback.message.text or "", max_length=3700, suffix="...(tronqué)")
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
    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)
    user_data = await state.get_data()
    last_question = user_data.get("last_question")
    if not last_question:
        await callback.answer(t("ticket_already_handled", lang), show_alert=False)
        return

    # Clear context upfront to prevent concurrent double-click ticket creation
    await state.clear()
    last_answer = user_data.get("last_answer", "Aucune réponse")

    user_id = callback.from_user.id
    user_handle = callback.from_user.username or callback.from_user.first_name or f"User_{user_id}"

    try:
        # Create ticket in backend and post its card to the admin/support group
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

        # Isolate message editing so that any display/markdown error never prevents group escalation
        base_text = callback.message.text or ""
        if len(base_text) > 3700:
            base_text = base_text[:3700] + "...(tronqué)"
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
