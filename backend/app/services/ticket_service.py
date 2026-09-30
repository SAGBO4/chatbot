from typing import Optional, List, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Ticket, TicketStatus, utc_now
from app.services.knowledge_base import KnowledgeBaseService


class TicketService:
    """Ticket persistence and lifecycle. Methods that change data commit, except `resolve_ticket(auto_commit=False)`."""

    @staticmethod
    async def create_ticket(
        session: AsyncSession,
        user_id: int,
        user_handle: Optional[str],
        question: str,
        automated_answer: Optional[str] = None,
        source_chat_id: Optional[int] = None,
        source_message_id: Optional[int] = None,
    ) -> Ticket:
        """Create an OPEN ticket."""
        ticket = Ticket(
            user_id=user_id,
            user_handle=user_handle,
            question=question.strip(),
            status=TicketStatus.OPEN.value,
            automated_answer=automated_answer,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket

    @staticmethod
    async def get_ticket(
        session: AsyncSession, ticket_id: int, user_id: Optional[int] = None
    ) -> Optional[Ticket]:
        """One ticket by id. With `user_id`, only if it belongs to that user (ownership check)."""
        query = select(Ticket).where(Ticket.id == ticket_id)
        if user_id is not None:
            query = query.where(Ticket.user_id == user_id)
        result = await session.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_all_tickets(
        session: AsyncSession,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Ticket]:
        """Tickets, newest first, optionally filtered by status and/or owner."""
        query = select(Ticket)
        if status:
            query = query.where(Ticket.status == status)
        if user_id is not None:
            query = query.where(Ticket.user_id == user_id)
        query = query.order_by(Ticket.id.desc()).limit(limit).offset(offset)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def attach_support_card(
        session: AsyncSession, ticket_id: int, message_id: int
    ) -> Optional[Ticket]:
        """
        Records the Telegram message id of the ticket card posted to the
        Support Group, so a later reply can be matched by message identity
        rather than by parsing the card's text.
        """
        ticket = await TicketService.get_ticket(session, ticket_id)
        if not ticket:
            return None

        ticket.support_group_message_id = message_id
        await session.commit()
        await session.refresh(ticket)
        return ticket

    @staticmethod
    async def get_ticket_by_support_message_id(
        session: AsyncSession, message_id: int
    ) -> Optional[Ticket]:
        """The ticket whose support-group card has this Telegram message id."""
        result = await session.execute(
            select(Ticket).where(Ticket.support_group_message_id == message_id)
        )
        return result.scalars().first()

    @staticmethod
    async def resolve_ticket(
        session: AsyncSession,
        ticket_id: int,
        solution: str,
        resolved_by: Optional[str] = None,
        resolution_channel: str = "TELEGRAM",
        add_to_knowledge_base: bool = True,
        auto_commit: bool = True,
        preloaded_ticket: Optional[Ticket] = None,
    ) -> Tuple[Optional[Ticket], bool]:
        """
        Resolve a ticket and return `(ticket, is_newly_resolved)`; `(None, False)` if it does not exist.

        An already resolved ticket is returned untouched with `False`, so callers do not repeat
        notifications. `preloaded_ticket` lets a batch caller skip the lookup; `auto_commit=False`
        leaves the commit to the caller.
        """
        ticket = preloaded_ticket or await TicketService.get_ticket(session, ticket_id)
        if not ticket:
            return None, False

        if ticket.status == TicketStatus.RESOLVED.value:
            return ticket, False

        # Claim the ticket with a conditional UPDATE instead of trusting the status read above: two
        # agents answering at the same time both read OPEN, and only one UPDATE can still match
        # `status != RESOLVED` (the database serialises them on the row). The loser is handed the
        # winner's resolution and `False`, so nobody is notified twice or overwritten.
        claim = await session.execute(
            update(Ticket)
            .where(Ticket.id == ticket.id, Ticket.status != TicketStatus.RESOLVED.value)
            .values(
                status=TicketStatus.RESOLVED.value,
                solution=solution.strip(),
                resolved_by=resolved_by,
                resolution_channel=resolution_channel,
                resolved_at=utc_now(),
            )
        )
        if claim.rowcount == 0:
            await session.refresh(ticket)
            return ticket, False
        await session.refresh(ticket)  # take the stored values (the UPDATE bypassed the object)

        # Feedback loop: dynamically ingest new solution into Knowledge Base
        if add_to_knowledge_base:
            await KnowledgeBaseService.add_article(
                session=session,
                question=ticket.question,
                solution=ticket.solution,
                keywords=None,
                source_ticket_id=ticket.id,
                auto_commit=False,
            )

        if auto_commit:
            await session.commit()
            await session.refresh(ticket)
        return ticket, True
