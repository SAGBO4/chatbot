import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from backend.config import settings
from bot.keyboards import get_resolution_keyboard
from bot.api_client import BackendClient
from bot.utils import escape_telegram_markdown

logger = logging.getLogger(__name__)
user_router = Router()


class UserQueryState(StatesGroup):
    waiting_for_resolution = State()


WELCOME_TEXT = (
    "👋 **Bonjour et bienvenue sur notre service de support automatisé !**\n\n"
    "Posez-moi simplement votre question dans ce chat, et je chercherai immédiatement "
    "la solution la plus adaptée dans notre base de connaissances.\n\n"
    "Si la réponse ne vous convient pas, vous pourrez transférer votre demande "
    "à notre équipe humaine en un clic !"
)

HELP_TEXT = (
    "ℹ️ **Aide**\n\n"
    "- Envoyez votre message texte décrivant votre problème.\n"
    "- Après réception de la réponse, cliquez sur **OUI** si votre problème est résolu, "
    "ou sur **NON** pour créer automatiquement un ticket auprès de notre équipe support."
)


@user_router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME_TEXT, parse_mode="Markdown")


@user_router.message(Command("help"))
async def handle_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="Markdown")


@user_router.message(F.chat.type == "private", F.text)
async def handle_user_query(
    message: Message,
    state: FSMContext,
    backend_client: Optional[BackendClient] = None,
):
    client = backend_client or BackendClient()
    user_query = message.text.strip()
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

        reply_text = (
            f"🤖 **Réponse :**\n\n{answer}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"❓ **Votre problème est-il résolu ?**"
        )
        if len(reply_text) > 4000:
            reply_text = reply_text[:4000] + "...(tronqué)"
        try:
            await message.answer(reply_text, reply_markup=get_resolution_keyboard(), parse_mode="Markdown")
        except Exception as send_err:
            logger.warning("Failed to send answer in markdown, falling back to plain text: %s", send_err)
            plain_reply = (
                f"🤖 Réponse :\n\n{answer}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"❓ Votre problème est-il résolu ?"
            )
            if len(plain_reply) > 4000:
                plain_reply = plain_reply[:4000] + "...(tronqué)"
            await message.answer(plain_reply, reply_markup=get_resolution_keyboard())
        await state.set_state(UserQueryState.waiting_for_resolution)

    except Exception as exc:
        logger.error("Error querying backend: %s", exc)
        await message.answer(
            "⚠️ Une erreur est survenue lors de la communication avec le serveur. "
            "Veuillez réessayer ultérieurement."
        )


@user_router.callback_query(F.data.startswith("resolve:yes"))
async def handle_resolve_yes(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Merci pour votre retour !")
    await callback.message.edit_text(
        f"{callback.message.text}\n\n"
        f"✅ **Statut : Problème résolu.**\n"
        f"Merci d'avoir utilisé notre service support ! N'hésitez pas si vous avez d'autres questions. 👋",
        reply_markup=None,
        parse_mode="Markdown",
    )


@user_router.callback_query(F.data.startswith("resolve:no"))
async def handle_resolve_no(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    client = backend_client or BackendClient()
    user_data = await state.get_data()
    last_question = user_data.get("last_question", "Question non spécifiée")
    last_answer = user_data.get("last_answer", "Aucune réponse")

    user_id = callback.from_user.id
    user_handle = callback.from_user.username or callback.from_user.first_name or f"User_{user_id}"

    try:
        # Create ticket in backend
        ticket = await client.create_ticket(
            user_id=user_id,
            user_handle=user_handle,
            question=last_question,
            automated_answer=last_answer,
        )
        ticket_id = ticket["id"]

        await state.clear()
        await callback.answer("Ticket créé !")
        await callback.message.edit_text(
            f"{callback.message.text}\n\n"
            f"🎟️ **Ticket #{ticket_id} créé et escaladé.**\n"
            f"Notre équipe support a été notifiée et vous répondra directement ici dès qu'un agent aura pris en charge votre demande.",
            reply_markup=None,
            parse_mode="Markdown",
        )

        # Notify Telegram Support Group
        support_group_id = settings.TELEGRAM_SUPPORT_GROUP_ID
        if settings.support_group_is_configured():
            safe_handle = escape_telegram_markdown(user_handle)
            safe_question = escape_telegram_markdown(last_question)
            safe_answer = escape_telegram_markdown(last_answer)
            group_card = (
                f"🚨 **NOUVEAU TICKET SUPPORT #{ticket_id}**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Utilisateur :** @{safe_handle} (`ID: {user_id}`)\n"
                f"❓ **Question :**\n{safe_question}\n\n"
                f"🤖 **Réponse automatique :**\n{safe_answer}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👉 *Pour répondre, répondez directement à ce message avec votre solution.*"
            )
            try:
                sent_card = await bot.send_message(
                    chat_id=support_group_id,
                    text=group_card,
                    parse_mode="Markdown",
                )
            except Exception as send_err:
                logger.warning("Failed to send markdown group card, falling back to plain text: %s", send_err)
                plain_card = (
                    f"🚨 NOUVEAU TICKET SUPPORT #{ticket_id}\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 Utilisateur : @{user_handle} (ID: {user_id})\n"
                    f"❓ Question :\n{last_question}\n\n"
                    f"🤖 Réponse automatique :\n{last_answer}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"👉 Pour répondre, répondez directement à ce message avec votre solution."
                )
                sent_card = await bot.send_message(
                    chat_id=support_group_id,
                    text=plain_card,
                )

            # Best-effort: record the card's message id so a reply can later
            # be matched by message identity rather than by parsing its text.
            # Failure here must not block the ticket/escalation flow - the
            # regex-based fallback in support_handlers.py still covers it.
            try:
                await client.attach_support_card(
                    ticket_id=ticket_id, message_id=sent_card.message_id
                )
            except Exception as attach_exc:
                logger.warning(
                    "Could not attach support card message id for ticket %s: %s",
                    ticket_id, attach_exc,
                )
    except Exception as exc:
        logger.error("Error creating or escalating ticket: %s", exc)
        await callback.answer("Erreur lors de la création du ticket", show_alert=True)
