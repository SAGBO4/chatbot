from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.i18n import SUPPORTED_LANGUAGES, t
from app.schemas import QueryResponse
from app.services.ai_assistant import AIAssistantService
from app.services.bot_settings_service import BotSettingsService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.specialized_agents import AgentCoordinator


class QueryOrchestrator:
    """Answers a user question from the knowledge base using language-specialized support agents."""

    @staticmethod
    async def process_query(
        session: AsyncSession,
        query: str,
        user_id: Optional[int] = None,
        user_handle: Optional[str] = None,
        language: Optional[str] = None,
    ) -> QueryResponse:
        """
        Search the knowledge base and answer using the specialized agent corresponding
        to the configured language (or explicit language parameter).

        Ensures that responses are strictly monolingual in French or English, preventing
        duplicate bilingual responses.
        """
        clean_query = query.strip()
        configured_language = await BotSettingsService.get_language(session)
        target_language = language if language in SUPPORTED_LANGUAGES else configured_language

        if not clean_query:
            return QueryResponse(
                query=query,
                found=False,
                confidence=0.0,
                answer=t("query_empty", target_language),
                article_id=None,
                requires_resolution_confirmation=False,
            )

        # 1. Search knowledge base
        matches = await KnowledgeBaseService.search(
            session=session,
            query=clean_query,
            threshold=settings.KB_CONFIDENCE_THRESHOLD,
            limit=AIAssistantService.CONTEXT_ARTICLES,
        )

        if not matches:
            return QueryResponse(
                query=clean_query,
                found=False,
                confidence=0.0,
                answer=t("query_no_match", target_language),
                article_id=None,
                requires_resolution_confirmation=True,
            )

        best_article, confidence = matches[0]

        # 2. Delegate to the specialized agent for target_language
        agent = AgentCoordinator.get_agent(target_language)
        answer = await agent.answer_query(clean_query, matches)

        return QueryResponse(
            query=clean_query,
            found=True,
            confidence=confidence,
            answer=answer,
            article_id=best_article.id,
            requires_resolution_confirmation=True,
        )

