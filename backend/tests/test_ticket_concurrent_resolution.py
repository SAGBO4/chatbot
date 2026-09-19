"""Two agents resolving the same ticket at the same time: exactly one of them wins."""
import asyncio

import pytest
from sqlalchemy import select

from app.models import Ticket, TicketStatus
from app.services.ticket_service import TicketService


@pytest.mark.asyncio
async def test_only_one_of_two_simultaneous_resolutions_is_newly_resolved(app_test_env, monkeypatch):
    """
    Both agents read the ticket as OPEN before either writes (forced with a barrier, which is what
    two overlapping requests look like). Each used to be told it resolved the ticket, so the user was
    notified twice and the loser's solution silently overwrote the winner's.
    """
    _, session_maker, _ = app_test_env
    async with session_maker() as session:
        ticket = await TicketService.create_ticket(session, user_id=1, user_handle="u", question="How do I reset?")
        ticket_id = ticket.id

    barrier = asyncio.Barrier(2)
    real_get_ticket = TicketService.get_ticket

    async def get_ticket_then_wait(session, ticket_id):
        found = await real_get_ticket(session, ticket_id)
        await barrier.wait()  # both agents have now seen the ticket as OPEN
        return found

    monkeypatch.setattr(TicketService, "get_ticket", staticmethod(get_ticket_then_wait))

    async def resolve_as(agent: str):
        async with session_maker() as session:
            return await TicketService.resolve_ticket(session, ticket_id, f"fix by {agent}", resolved_by=agent)

    outcomes = await asyncio.gather(resolve_as("A"), resolve_as("B"))

    assert sorted(is_new for _, is_new in outcomes) == [False, True]
    winner = next(agent for agent, (_, is_new) in zip("AB", outcomes) if is_new)
    for _, (returned, _) in zip("AB", outcomes):
        assert returned.resolved_by == winner, "the loser must be handed the winner's resolution"

    async with session_maker() as session:
        stored = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one()
    assert stored.status == TicketStatus.RESOLVED.value
    assert stored.resolved_by == winner
    assert stored.solution == f"fix by {winner}"
