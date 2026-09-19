"""Support tickets: create, read, attach the support-group card, resolve."""
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.background import safe_background_task
from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models import TicketStatus
from app.observability import get_logger
from app.schemas import TicketCreateRequest, TicketResolveRequest, TicketResponse, TicketSupportCardRequest
from app.security import verify_api_key
from app.services.bot_settings_service import BotSettingsService
from app.services.email_service import EmailService
from app.services.ticket_service import TicketService

logger = get_logger(__name__)
router = APIRouter(tags=["tickets"])


@router.post(
    "/api/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
async def create_ticket(
    request: Request,
    payload: TicketCreateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    """Open a support ticket; the support team is emailed in the background when email is enabled."""
    ticket = await TicketService.create_ticket(
        session=session,
        user_id=payload.user_id,
        user_handle=payload.user_handle,
        question=payload.question,
        automated_answer=payload.automated_answer,
    )

    if settings.is_email_configured():
        background_tasks.add_task(
            safe_background_task,
            EmailService.send_ticket_created_notification,
            ticket_id=ticket.id,
            user_handle=ticket.user_handle,
            user_id=ticket.user_id,
            question=ticket.question,
            automated_answer=ticket.automated_answer,
            lang=await BotSettingsService.get_language(session),
        )

    return ticket


@router.get("/api/tickets", response_model=List[TicketResponse], dependencies=[Depends(verify_api_key)])
async def list_tickets(
    status_filter: Optional[TicketStatus] = None,
    user_id: Optional[int] = Query(default=None, description="Filter tickets by user ID"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """List tickets, optionally filtered by status or `user_id`; paginated."""
    status_val = status_filter.value if status_filter else None
    return await TicketService.get_all_tickets(
        session=session,
        status=status_val,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/api/tickets/by-support-message/{message_id}",
    response_model=TicketResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_ticket_by_support_message(
    message_id: int,
    session: AsyncSession = Depends(get_db),
):
    """
    Looks up a ticket by the Telegram message id of its support-group card,
    so an agent's reply can be matched by message identity rather than by
    parsing the card's text.
    """
    ticket = await TicketService.get_ticket_by_support_message_id(
        session=session, message_id=message_id
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="No ticket found for this support message id")
    return ticket


@router.get(
    "/api/tickets/{ticket_id}",
    response_model=TicketResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_ticket(
    ticket_id: int,
    user_id: Optional[int] = Query(default=None, description="Optional user ID to enforce ownership scoping"),
    session: AsyncSession = Depends(get_db),
):
    """Get one ticket. With `user_id`, a ticket belonging to another user is reported as not found."""
    ticket = await TicketService.get_ticket(session=session, ticket_id=ticket_id, user_id=user_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post(
    "/api/tickets/{ticket_id}/support-card",
    response_model=TicketResponse,
    dependencies=[Depends(verify_api_key)],
)
async def attach_support_card(
    ticket_id: int,
    payload: TicketSupportCardRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Records the Telegram message id of the ticket card posted to the Support
    Group, so a later agent reply can be resolved by message identity.
    """
    ticket = await TicketService.attach_support_card(
        session=session, ticket_id=ticket_id, message_id=payload.message_id
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post(
    "/api/tickets/{ticket_id}/resolve",
    response_model=TicketResponse,
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("15/minute")
async def resolve_ticket(
    request: Request,
    ticket_id: int,
    payload: TicketResolveRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    """
    Resolve a ticket and, by default, add its solution to the knowledge base.

    `is_newly_resolved` is false when another agent had already resolved it.
    """
    channel = payload.resolution_channel or "TELEGRAM"
    ticket, newly_resolved = await TicketService.resolve_ticket(
        session=session,
        ticket_id=ticket_id,
        solution=payload.solution,
        resolved_by=payload.resolved_by,
        resolution_channel=channel,
        add_to_knowledge_base=payload.add_to_knowledge_base,
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # If newly resolved on Telegram, inform the email channel if configured
    if newly_resolved and channel.upper() == "TELEGRAM" and settings.is_email_configured():
        background_tasks.add_task(
            safe_background_task,
            EmailService.send_ticket_resolved_notification,
            ticket_id=ticket.id,
            resolved_by=ticket.resolved_by,
            resolution_channel="TELEGRAM",
            solution=ticket.solution,
            lang=await BotSettingsService.get_language(session),
        )

    res = TicketResponse.model_validate(ticket)
    res.is_newly_resolved = newly_resolved
    return res
