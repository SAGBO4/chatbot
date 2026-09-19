"""Resolving a ticket from an inbound support reply email (shared by the generic and Brevo webhooks)."""
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.background import safe_background_task
from app.config import settings
from app.email_parsing import clean_email_reply_body, find_ticket_id
from app.i18n import t
from app.models import Ticket
from app.schemas import MAX_SOLUTION_LENGTH, BrevoInboundItem
from app.services.bot_settings_service import BotSettingsService
from app.services.telegram_relay import TelegramRelay
from app.services.ticket_service import TicketService
from app.telegram_text import escape_telegram_markdown, truncate_telegram_text


async def resolve_inbound_email(
    session: AsyncSession,
    background_tasks: BackgroundTasks,
    sender: str,
    subject: str,
    body: str,
    auto_commit: bool = True,
    preloaded_ticket: Optional[Ticket] = None,
) -> Dict[str, Any]:
    """
    Resolve a ticket from an inbound support reply email, whichever webhook delivered it
    (the generic HMAC endpoint or Brevo's batch endpoint).

    Extracts the ticket id from the subject, resolves the ticket, forwards the solution to the
    user on Telegram, notifies the support group and feeds the knowledge base.

    Never raises for expected problems: it returns a dict whose `status` is one of
    `unauthorized_sender`, `no_ticket_reference`, `empty_body`, `ticket_not_found`,
    `already_resolved` or `resolved`, so a batch caller can carry on with its other items and a
    single-item caller can map the status to an HTTP error.
    """
    if not settings.is_authorized_email_sender(sender):
        return {
            "status": "unauthorized_sender",
            "ticket_id": None,
            "message": f"Sender '{sender}' is not authorized to resolve tickets via email.",
        }

    ticket_id = find_ticket_id(subject)
    if ticket_id is None:
        return {
            "status": "no_ticket_reference",
            "ticket_id": None,
            "message": "Could not identify Ticket ID in email subject (expected '[Ticket #123]').",
        }

    clean_solution = clean_email_reply_body(body)

    if not clean_solution:
        return {
            "status": "empty_body",
            "ticket_id": ticket_id,
            "message": (
                f"Email reply for Ticket #{ticket_id} had no content once quoted "
                "thread history was stripped; ticket left unresolved."
            ),
        }

    # Same cap as TicketResolveRequest.solution
    clean_solution = truncate_telegram_text(clean_solution, max_length=MAX_SOLUTION_LENGTH, suffix="")

    ticket, newly_resolved = await TicketService.resolve_ticket(
        session=session,
        ticket_id=ticket_id,
        solution=clean_solution,
        resolved_by=sender,
        resolution_channel="EMAIL",
        add_to_knowledge_base=True,
        auto_commit=auto_commit,
        preloaded_ticket=preloaded_ticket,
    )

    if not ticket:
        return {
            "status": "ticket_not_found",
            "ticket_id": ticket_id,
            "message": f"Ticket #{ticket_id} not found.",
        }

    if not newly_resolved:
        return {
            "status": "already_resolved",
            "ticket_id": ticket_id,
            "message": f"Ticket #{ticket_id} was already resolved by {ticket.resolved_by} via {ticket.resolution_channel}.",
        }

    # Solution and sender come from an email: escape their Markdown before wrapping them in our own
    # formatting, or an unbalanced `*`, `_` or backtick makes Telegram reject the whole message (400)
    # after the ticket is already marked resolved.
    safe_solution = escape_telegram_markdown(clean_solution)
    safe_sender = escape_telegram_markdown(sender)

    lang = await BotSettingsService.get_language(session)
    user_text = t("email_reply_to_user", lang, ticket_id=ticket_id, solution=safe_solution, sender=safe_sender)
    user_text = truncate_telegram_text(user_text, max_length=4000, lang=lang)
    background_tasks.add_task(
        safe_background_task,
        TelegramRelay.send_message_to_user,
        ticket.user_id,
        user_text,
    )

    # 2. Inform the Telegram Support Group that the ticket was resolved via email
    group_notification = t("email_resolved_group_notice", lang, ticket_id=ticket_id, sender=safe_sender, user_id=ticket.user_id)
    background_tasks.add_task(
        safe_background_task,
        TelegramRelay.notify_support_group,
        group_notification,
    )

    return {
        "status": "resolved",
        "ticket_id": ticket_id,
        "resolved_by": sender,
        "channel": "EMAIL",
    }


def select_brevo_body(item: BrevoInboundItem) -> str:
    """
    Pick a Brevo item's own quote-stripped extraction when present, else its raw text body.

    Either way `clean_email_reply_body` runs on it afterwards, as a second pass in case Brevo's
    extraction misses a quote marker.
    """
    if item.ExtractedMarkdownMessage and item.ExtractedMarkdownMessage.strip():
        return item.ExtractedMarkdownMessage
    return item.RawTextBody or ""
