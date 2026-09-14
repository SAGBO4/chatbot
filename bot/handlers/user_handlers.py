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
from bot.utils import escape_telegram_markdown, truncate_telegram_text, TELEGRAM_MAX_MESSAGE_LENGTH

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
    if len(user_query) > TELEGRAM_MAX_MESSAGE_LENGTH:
        await message.answer(
            f"⚠️ Votre question est trop longue (maximum {TELEGRAM_MAX_MESSAGE_LENGTH} caractères). "
            "Veuillez raccourcir votre message et réessayer."
        )
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

        reply_text = (
            f"🤖 **Réponse :**\n\n{answer}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"❓ **Votre problème est-il résolu ?**"
        )
        reply_text = truncate_telegram_text(reply_text, max_length=4000, suffix="...(tronqué)")
        try:
            await message.answer(reply_text, reply_markup=get_resolution_keyboard(), parse_mode="Markdown")
        except Exception as send_err:
            logger.warning("Failed to send answer in markdown, falling back to plain text: %s", send_err)
            plain_reply = (
                f"🤖 Réponse :\n\n{answer}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"❓ Votre problème est-il résolu ?"
            )
            plain_reply = truncate_telegram_text(plain_reply, max_length=4000, suffix="...(tronqué)")
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
    base_text = truncate_telegram_text(callback.message.text or "", max_length=3700, suffix="...(tronqué)")
    resolved_notice = (
        f"{base_text}\n\n"
        f"✅ **Statut : Problème résolu.**\n"
        f"Merci d'avoir utilisé notre service support ! N'hésitez pas si vous avez d'autres questions. 👋"
    )
    try:
        await callback.message.edit_text(
            resolved_notice,
            reply_markup=None,
            parse_mode="Markdown",
        )
    except Exception as edit_err:
        logger.warning("Markdown edit_text failed in resolve_yes, falling back to plain text: %s", edit_err)
        plain_notice = (
            f"{base_text}\n\n"
            f"✅ Statut : Problème résolu.\n"
            f"Merci d'avoir utilisé notre service support ! N'hésitez pas si vous avez d'autres questions. 👋"
        )
        try:
            await callback.message.edit_text(plain_notice, reply_markup=None)
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
    user_data = await state.get_data()
    last_question = user_data.get("last_question")
    if not last_question:
        await callback.answer("Cette demande a déjà été prise en compte.", show_alert=False)
        return

    # Clear context upfront to prevent concurrent double-click ticket creation
    await state.clear()
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

        await callback.answer("Ticket créé !")

        # Isolate message editing so that any display/markdown error never prevents group escalation
        base_text = callback.message.text or ""
        if len(base_text) > 3700:
            base_text = base_text[:3700] + "...(tronqué)"
        confirmation_text = (
            f"{base_text}\n\n"
            f"🎟️ **Ticket #{ticket_id} créé et escaladé.**\n"
            f"Notre équipe support a été notifiée et vous répondra directement ici dès qu'un agent aura pris en charge votre demande."
        )
        try:
            await callback.message.edit_text(
                confirmation_text,
                reply_markup=None,
                parse_mode="Markdown",
            )
        except Exception as edit_err:
            logger.warning("Markdown edit_text failed in resolve_no, retrying in plain text: %s", edit_err)
            plain_confirmation = (
                f"{base_text}\n\n"
                f"🎟️ Ticket #{ticket_id} créé et escaladé.\n"
                f"Notre équipe support a été notifiée et vous répondra directement ici dès qu'un agent aura pris en charge votre demande."
            )
            try:
                await callback.message.edit_text(plain_confirmation, reply_markup=None)
            except Exception as e:
                logger.warning("Failed to edit user message in resolve_no: %s", e)

        # Notify Telegram Support Group
        support_group_id = settings.TELEGRAM_SUPPORT_GROUP_ID
        if settings.support_group_is_configured():
            # Truncate fields if excessively long to ensure group card never overflows Telegram 4096 limit
            card_question = truncate_telegram_text(last_question, max_length=1000, suffix="...")
            card_answer = truncate_telegram_text(last_answer, max_length=1800, suffix="...")

            safe_handle = escape_telegram_markdown(user_handle)
            safe_question = escape_telegram_markdown(card_question)
            safe_answer = escape_telegram_markdown(card_answer)
            group_card = (
                f"🚨 **NOUVEAU TICKET SUPPORT #{ticket_id}**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Utilisateur :** @{safe_handle} (`ID: {user_id}`)\n"
                f"❓ **Question :**\n{safe_question}\n\n"
                f"🤖 **Réponse automatique :**\n{safe_answer}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👉 *Pour répondre, répondez directement à ce message avec votre solution.*"
            )
            sent_card = None
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
                    f"❓ Question :\n{card_question}\n\n"
                    f"🤖 Réponse automatique :\n{card_answer}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"👉 Pour répondre, répondez directement à ce message avec votre solution."
                )
                try:
                    sent_card = await bot.send_message(
                        chat_id=support_group_id,
                        text=plain_card,
                    )
                except Exception as plain_err:
                    logger.error("Failed to send plain text group card: %s", plain_err)

            # Best-effort: record the card's message id so a reply can later
            # be matched by message identity rather than by parsing its text.
            if sent_card and hasattr(sent_card, "message_id"):
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
