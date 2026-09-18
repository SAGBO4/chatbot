import logging
from aiogram import Bot
from app.config import settings
from bot.api_client import BackendClient
from bot.utils import escape_telegram_markdown, truncate_telegram_text

logger = logging.getLogger(__name__)


async def create_ticket_and_notify_admin_group(
    client: BackendClient,
    bot: Bot,
    user_id: int,
    user_handle: str,
    question: str,
    automated_answer: str,
) -> dict:
    """
    Create a ticket through the backend and post its card to the admin/support group.

    Shared by the private-chat and community-group escalation flows, so the card and its
    Markdown-to-plain-text fallback exist once. Ticket details only ever go to the admin group here;
    callers decide what to show in their own chat. Returns the ticket dict from the backend.
    """
    ticket = await client.create_ticket(
        user_id=user_id,
        user_handle=user_handle,
        question=question,
        automated_answer=automated_answer,
    )
    ticket_id = ticket["id"]

    support_group_id = settings.TELEGRAM_SUPPORT_GROUP_ID
    if not settings.support_group_is_configured():
        return ticket

    # Cut long fields so the card stays under Telegram's 4096-character limit
    card_question = truncate_telegram_text(question, max_length=1000, suffix="...")
    card_answer = truncate_telegram_text(automated_answer, max_length=1800, suffix="...")

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

    # Best effort: store the card's message id so a reply can be matched to the ticket by identity
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

    return ticket
