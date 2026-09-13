import re
import logging
from typing import Optional, Union
from aiogram import Router, F, Bot
from aiogram.types import Message
from backend.config import settings
from bot.api_client import BackendClient

logger = logging.getLogger(__name__)
support_router = Router()

TICKET_ID_REGEX = re.compile(r"TICKET SUPPORT #(\d+)")
USER_ID_REGEX = re.compile(r"ID:\s*(\d+)")


def _is_support_group_chat(chat_id: Union[int, str]) -> bool:
    """
    Returns True only if chat_id matches the configured Telegram Support Group.

    Returns False when TELEGRAM_SUPPORT_GROUP_ID is unconfigured (falsy or the
    "0" sentinel), so an unconfigured group can never accidentally match.
    """
    group_id = settings.TELEGRAM_SUPPORT_GROUP_ID
    if not group_id or str(group_id) == "0":
        return False
    return str(chat_id) == str(group_id)


@support_router.message(F.reply_to_message)
async def handle_support_agent_reply(
    message: Message,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """
    Captures replies made by support team agents to ticket cards posted in the support group.

    Only replies sent in the configured Telegram Support Group are treated as
    agent resolutions; replies from any other chat (private DMs included) are
    ignored to prevent unauthenticated users from resolving arbitrary tickets,
    messaging arbitrary Telegram users, or injecting content into the
    knowledge base.
    """
    if not _is_support_group_chat(message.chat.id):
        return

    client = backend_client or BackendClient()

    # 1. Primary: resolve by the replied-to message's identity, so wording
    # changes to the card's text can never break matching.
    ticket_id: Optional[int] = None
    target_user_id: Optional[int] = None

    try:
        matched_ticket = await client.get_ticket_by_support_message(
            message.reply_to_message.message_id
        )
    except Exception as exc:
        logger.warning("Support-card lookup by message id failed, falling back to text: %s", exc)
        matched_ticket = None

    if matched_ticket:
        ticket_id = matched_ticket["id"]
        target_user_id = matched_ticket.get("user_id")
    else:
        # 2. Fallback: parse the card's text (covers tickets created before
        # this lookup existed, or a card whose id was never recorded).
        replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        ticket_match = TICKET_ID_REGEX.search(replied_text)
        user_match = USER_ID_REGEX.search(replied_text)

        if ticket_match:
            ticket_id = int(ticket_match.group(1))
            target_user_id = int(user_match.group(1)) if user_match else None

    # 3. Neither the id-based lookup nor the text fallback found a ticket:
    # tell the agent explicitly instead of silently doing nothing.
    if ticket_id is None:
        await message.reply(
            "⚠️ Je n'ai pas pu associer ce message à un ticket. "
            "Répondez directement au message de la carte du ticket pour le résoudre."
        )
        return

    solution_text = message.text.strip()
    agent_name = (
        message.from_user.username
        or f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        or f"Agent_{message.from_user.id}"
    )

    try:
        # Resolve ticket and trigger KB ingestion
        resolved_ticket = await client.resolve_ticket(
            ticket_id=ticket_id,
            solution=solution_text,
            resolved_by=agent_name,
            add_to_knowledge_base=True,
        )

        user_id = target_user_id or resolved_ticket.get("user_id")

        # 1. Forward the solution to the user via Telegram
        if user_id:
            user_notification = (
                f"📬 **Réponse de l'équipe support (Ticket #{ticket_id})**\n\n"
                f"{solution_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"Traité par : *{agent_name}*\n"
                f"Merci de votre confiance ! 👋"
            )
            await bot.send_message(
                chat_id=user_id,
                text=user_notification,
                parse_mode="Markdown",
            )

        # 2. Confirm to the support team in group
        await message.reply(
            f"✅ **Ticket #{ticket_id} résolu !**\n"
            f"• La réponse a été transmise à l'utilisateur (`ID: {user_id}`).\n"
            f"• La solution a été automatiquement intégrée dans la base de connaissances.",
            parse_mode="Markdown",
        )

    except Exception as exc:
        logger.error("Error resolving ticket %s via group reply: %s", ticket_id, exc)
        await message.reply(
            f"❌ **Erreur lors de la résolution du ticket #{ticket_id}** : {exc}"
        )
