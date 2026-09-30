"""Answering a user question."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.limiter import limiter
from app.observability import get_logger
from app.openapi_docs import PROTECTED, RATE_LIMITED
from app.schemas import QueryRequest, QueryResponse
from app.security import verify_api_key
from app.services.query_orchestrator import QueryOrchestrator

logger = get_logger(__name__)
router = APIRouter(tags=["query"], responses={**PROTECTED, **RATE_LIMITED})


@router.post("/api/query", response_model=QueryResponse, dependencies=[Depends(verify_api_key)])
@limiter.limit("30/minute")
async def handle_query(
    request: Request,
    payload: QueryRequest,
    session: AsyncSession = Depends(get_db),
):
    """Answer a user's question from the knowledge base (and the optional AI), with a confidence score."""
    return await QueryOrchestrator.process_query(
        session=session,
        query=payload.query,
        user_id=payload.user_id,
        user_handle=payload.user_handle,
        language=payload.language,
    )

