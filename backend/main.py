import re
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db, init_db
from backend.schemas import (
    QueryRequest,
    QueryResponse,
    TicketCreateRequest,
    TicketResponse,
    TicketResolveRequest,
    KnowledgeIngestRequest,
    KnowledgeArticleResponse,
    InboundEmailWebhookRequest,
)
from backend.services.query_orchestrator import QueryOrchestrator
from backend.services.ticket_service import TicketService
from backend.services.knowledge_base import KnowledgeBaseService
from backend.services.email_service import EmailService
from backend.services.telegram_relay import TelegramRelay

TICKET_SUBJECT_REGEX = re.compile(r"Ticket\s*#(\d+)", re.IGNORECASE)


def clean_email_reply_body(body: str) -> str:
    """Strips email thread history and quote lines."""
    lines = body.splitlines()
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Common email quote markers
        if stripped.startswith(">") or stripped.startswith("---"):
            break
        if re.search(r"^(On\s+.+wrote:|Le\s+.+a écrit\s*:)", stripped, re.IGNORECASE):
            break
        clean_lines.append(line)
    result = "\n".join(clean_lines).strip()
    return result if result else body.strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Telegram Support Bot Backend API",
    description="Backend API for telegram support bot with knowledge base, multi-channel ticketing and email sync",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "support-bot-backend"}


@app.post("/api/query", response_model=QueryResponse)
async def handle_query(
    payload: QueryRequest,
    session: AsyncSession = Depends(get_db),
):
    return await QueryOrchestrator.process_query(
        session=session,
        query=payload.query,
        user_id=payload.user_id,
        user_handle=payload.user_handle,
    )


@app.post("/api/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    ticket = await TicketService.create_ticket(
        session=session,
        user_id=payload.user_id,
        user_handle=payload.user_handle,
        question=payload.question,
        automated_answer=payload.automated_answer,
    )

    # Multi-channel alert: dispatch email notification to support team in the background
    background_tasks.add_task(
        EmailService.send_ticket_created_notification,
        ticket_id=ticket.id,
        user_handle=ticket.user_handle,
        user_id=ticket.user_id,
        question=ticket.question,
        automated_answer=ticket.automated_answer,
    )

    return ticket


@app.get("/api/tickets", response_model=List[TicketResponse])
async def list_tickets(
    status_filter: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    return await TicketService.get_all_tickets(session=session, status=status_filter)


@app.get("/api/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: int,
    session: AsyncSession = Depends(get_db),
):
    ticket = await TicketService.get_ticket(session=session, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.post("/api/tickets/{ticket_id}/resolve", response_model=TicketResponse)
async def resolve_ticket(
    ticket_id: int,
    payload: TicketResolveRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
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

    # If newly resolved on Telegram, inform the email channel
    if newly_resolved and channel.upper() == "TELEGRAM":
        background_tasks.add_task(
            EmailService.send_ticket_resolved_notification,
            ticket_id=ticket.id,
            resolved_by=ticket.resolved_by,
            resolution_channel="TELEGRAM",
            solution=ticket.solution,
        )

    return ticket


@app.post("/api/webhooks/email-inbound")
async def handle_inbound_email(
    payload: InboundEmailWebhookRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    """
    Handles incoming support reply emails.
    Extracts ticket ID from subject ([Ticket #123]), resolves the ticket,
    delivers the answer to the user on Telegram, and updates the knowledge base.
    """
    match = TICKET_SUBJECT_REGEX.search(payload.subject)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Could not identify Ticket ID in email subject (expected '[Ticket #123]').",
        )

    ticket_id = int(match.group(1))
    clean_solution = clean_email_reply_body(payload.body)

    ticket, newly_resolved = await TicketService.resolve_ticket(
        session=session,
        ticket_id=ticket_id,
        solution=clean_solution,
        resolved_by=payload.sender,
        resolution_channel="EMAIL",
        add_to_knowledge_base=True,
    )

    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket #{ticket_id} not found.")

    if not newly_resolved:
        return {
            "status": "already_resolved",
            "ticket_id": ticket_id,
            "message": f"Ticket #{ticket_id} was already resolved by {ticket.resolved_by} via {ticket.resolution_channel}.",
        }

    # 1. Forward the solution to the user on Telegram
    user_text = (
        f"📬 **Réponse de l'équipe support par Email (Ticket #{ticket_id})**\n\n"
        f"{clean_solution}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Traité par : *{payload.sender}*\n"
        f"Merci de votre confiance ! 👋"
    )
    background_tasks.add_task(TelegramRelay.send_message_to_user, ticket.user_id, user_text)

    # 2. Inform the Telegram Support Group that the ticket was resolved via email
    group_notification = (
        f"✅ **Ticket #{ticket_id} résolu par Email !**\n"
        f"• Par : `{payload.sender}`\n"
        f"• La solution a été transmise à l'utilisateur (`ID: {ticket.user_id}`).\n"
        f"• La base de connaissances a été mise à jour automatiquement."
    )
    background_tasks.add_task(TelegramRelay.notify_support_group, group_notification)

    return {
        "status": "resolved",
        "ticket_id": ticket_id,
        "resolved_by": payload.sender,
        "channel": "EMAIL",
    }


@app.post("/api/knowledge/ingest", response_model=KnowledgeArticleResponse, status_code=status.HTTP_201_CREATED)
async def ingest_knowledge(
    payload: KnowledgeIngestRequest,
    session: AsyncSession = Depends(get_db),
):
    return await KnowledgeBaseService.add_article(
        session=session,
        question=payload.question,
        solution=payload.solution,
        keywords=payload.keywords,
        source_ticket_id=payload.source_ticket_id,
    )


@app.get("/api/knowledge", response_model=List[KnowledgeArticleResponse])
async def list_knowledge(
    session: AsyncSession = Depends(get_db),
):
    return await KnowledgeBaseService.get_all_articles(session=session)
