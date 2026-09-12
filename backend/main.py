from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
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
)
from backend.services.query_orchestrator import QueryOrchestrator
from backend.services.ticket_service import TicketService
from backend.services.knowledge_base import KnowledgeBaseService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    await init_db()
    yield


app = FastAPI(
    title="Telegram Support Bot Backend API",
    description="Backend API for telegram support bot with knowledge base and ticketing",
    version="1.0.0",
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
    """Processes an incoming user query against the Knowledge Base and optional AI."""
    response = await QueryOrchestrator.process_query(
        session=session,
        query=payload.query,
        user_id=payload.user_id,
        user_handle=payload.user_handle,
    )
    return response


@app.post("/api/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    """Creates a new support ticket when an issue is not resolved."""
    ticket = await TicketService.create_ticket(
        session=session,
        user_id=payload.user_id,
        user_handle=payload.user_handle,
        question=payload.question,
        automated_answer=payload.automated_answer,
    )
    return ticket


@app.get("/api/tickets", response_model=List[TicketResponse])
async def list_tickets(
    status_filter: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """Lists support tickets, optionally filtered by status."""
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
    session: AsyncSession = Depends(get_db),
):
    """Resolves a ticket with a solution and automatically ingests into Knowledge Base."""
    ticket, newly_resolved = await TicketService.resolve_ticket(
        session=session,
        ticket_id=ticket_id,
        solution=payload.solution,
        resolved_by=payload.resolved_by,
        add_to_knowledge_base=payload.add_to_knowledge_base,
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.post("/api/knowledge/ingest", response_model=KnowledgeArticleResponse, status_code=status.HTTP_201_CREATED)
async def ingest_knowledge(
    payload: KnowledgeIngestRequest,
    session: AsyncSession = Depends(get_db),
):
    """Directly ingests a question-solution pair into the knowledge base."""
    article = await KnowledgeBaseService.add_article(
        session=session,
        question=payload.question,
        solution=payload.solution,
        keywords=payload.keywords,
        source_ticket_id=payload.source_ticket_id,
    )
    return article


@app.get("/api/knowledge", response_model=List[KnowledgeArticleResponse])
async def list_knowledge(
    session: AsyncSession = Depends(get_db),
):
    return await KnowledgeBaseService.get_all_articles(session=session)
