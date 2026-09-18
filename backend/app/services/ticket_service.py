from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Ticket, TicketStatus, utc_now
from app.services.knowledge_base import KnowledgeBaseService


class TicketService:
    @staticmethod
    async def create_ticket(
        session: AsyncSession,
        user_id: int,
        user_handle: Optional[str],
        question: str,
        automated_answer: Optional[str] = None,
    ) -> Ticket:
        ticket = Ticket(
            user_id=user_id,
            user_handle=user_handle,
            question=question.strip(),
            status=TicketStatus.OPEN.value,
            automated_answer=automated_answer,
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket

    @staticmethod
    async def get_ticket(
        session: AsyncSession, ticket_id: int, user_id: Optional[int] = None
    ) -> Optional[Ticket]:
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
        Resolve a ticket. Returns (ticket, is_newly_resolved).
        If already resolved, returns (ticket, False) to prevent duplicate actions.
        """
        ticket = preloaded_ticket or await TicketService.get_ticket(session, ticket_id)
        if not ticket:
            return None, False

        if ticket.status == TicketStatus.RESOLVED.value:
            return ticket, False

        ticket.status = TicketStatus.RESOLVED.value
        ticket.solution = solution.strip()
        ticket.resolved_by = resolved_by
        ticket.resolution_channel = resolution_channel
        ticket.resolved_at = utc_now()

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
