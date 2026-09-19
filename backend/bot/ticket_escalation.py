import logging
from aiogram import Bot
from app.config import settings
from app.i18n import DEFAULT_LANGUAGE, t
from bot.api_client import BackendClient
from bot.messaging import call_with_markdown_fallback
from app.telegram_text import escape_telegram_markdown, truncate_telegram_text

logger = logging.getLogger(__name__)


async def create_ticket_and_notify_admin_group(
    client: BackendClient,
    bot: Bot,
    user_id: int,
    user_handle: str,
    question: str,
    automated_answer: str,
    lang: str = DEFAULT_LANGUAGE,
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
    group_card = t(
        "admin_ticket_card", lang,
        ticket_id=ticket_id, handle=safe_handle, user_id=user_id, question=safe_question, answer=safe_answer,
    )
    plain_card = t(
        "admin_ticket_card_plain", lang,
        ticket_id=ticket_id, handle=user_handle, user_id=user_id, question=card_question, answer=card_answer,
    )
    sent_card = await call_with_markdown_fallback(
        bot.send_message, chat_id=support_group_id, text=group_card,
        plain_overrides={"text": plain_card},
        what="Support group card", swallow_failure=True, failure_level=logging.ERROR,
    )

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
