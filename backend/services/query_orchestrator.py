from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import settings
from backend.schemas import QueryResponse
from backend.services.knowledge_base import KnowledgeBaseService
from backend.services.ai_assistant import AIAssistantService

FALLBACK_NO_MATCH = (
    "Je n'ai pas trouvé de réponse directe à votre question dans notre base de connaissances. "
    "Souhaitez-vous que je transmette votre demande à notre équipe support ?"
)


class QueryOrchestrator:
    @staticmethod
    async def process_query(
        session: AsyncSession,
        query: str,
        user_id: Optional[int] = None,
        user_handle: Optional[str] = None,
    ) -> QueryResponse:
        clean_query = query.strip()
        if not clean_query:
            return QueryResponse(
                query=query,
                found=False,
                confidence=0.0,
                answer="Veuillez poser une question pour que je puisse vous aider.",
                article_id=None,
                requires_resolution_confirmation=False,
            )

        # 1. Search knowledge base
        matches = await KnowledgeBaseService.search(
            session=session,
            query=clean_query,
            threshold=settings.KB_CONFIDENCE_THRESHOLD,
            limit=3,
        )

        if not matches:
            return QueryResponse(
                query=clean_query,
                found=False,
                confidence=0.0,
                answer=FALLBACK_NO_MATCH,
                article_id=None,
                requires_resolution_confirmation=True,
            )

        best_article, confidence = matches[0]

        # 2. Check if AI synthesis is enabled
        answer = best_article.solution
        if settings.AI_ENABLED:
            ai_answer = await AIAssistantService.generate_answer(clean_query, matches)
            if ai_answer:
                answer = ai_answer

        return QueryResponse(
            query=clean_query,
            found=True,
            confidence=confidence,
            answer=answer,
            article_id=best_article.id,
            requires_resolution_confirmation=True,
        )
