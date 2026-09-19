"""Knowledge base articles."""
from typing import List

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.limiter import limiter
from app.observability import get_logger
from app.schemas import KnowledgeArticleResponse, KnowledgeIngestRequest
from app.security import verify_api_key
from app.services.knowledge_base import KnowledgeBaseService

logger = get_logger(__name__)
router = APIRouter(tags=["knowledge"])


@router.post(
    "/api/knowledge/ingest",
    response_model=KnowledgeArticleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("20/minute")
async def ingest_knowledge(
    request: Request,
    payload: KnowledgeIngestRequest,
    session: AsyncSession = Depends(get_db),
):
    """Add a knowledge base article manually."""
    return await KnowledgeBaseService.add_article(
        session=session,
        question=payload.question,
        solution=payload.solution,
        keywords=payload.keywords,
        source_ticket_id=payload.source_ticket_id,
    )


@router.get(
    "/api/knowledge",
    response_model=List[KnowledgeArticleResponse],
    dependencies=[Depends(verify_api_key)],
)
async def list_knowledge(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """List knowledge base articles; paginated."""
    return await KnowledgeBaseService.get_all_articles(session=session, limit=limit, offset=offset)
