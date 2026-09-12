import re
import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message
from bot.api_client import BackendClient

logger = logging.getLogger(__name__)
support_router = Router()

TICKET_ID_REGEX = re.compile(r"TICKET SUPPORT #(\d+)")
USER_ID_REGEX = re.compile(r"ID:\s*(\d+)")


@support_router.message(F.reply_to_message)
async def handle_support_agent_reply(
    message: Message,
    bot: Bot,
    backend_client: Optional[BackendClient] = None,
):
    """
    Captures replies made by support team agents to ticket cards posted in the support group.
    """
    replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    ticket_match = TICKET_ID_REGEX.search(replied_text)
    user_match = USER_ID_REGEX.search(replied_text)

    if not ticket_match:
        # Not a reply to a support ticket card, ignore
        return

    ticket_id = int(ticket_match.group(1))
    target_user_id = int(user_match.group(1)) if user_match else None

    solution_text = message.text.strip()
    agent_name = (
        message.from_user.username
        or f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        or f"Agent_{message.from_user.id}"
    )

    client = backend_client or BackendClient()

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
