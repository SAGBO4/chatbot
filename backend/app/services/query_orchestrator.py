from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.i18n import t
from app.schemas import QueryResponse
from app.services.ai_assistant import AIAssistantService
from app.services.bot_settings_service import BotSettingsService
from app.services.knowledge_base import KnowledgeBaseService


class QueryOrchestrator:
    """Answers a user question from the knowledge base, optionally rephrased by the AI."""

    @staticmethod
    async def process_query(
        session: AsyncSession,
        query: str,
        user_id: Optional[int] = None,
        user_handle: Optional[str] = None,
    ) -> QueryResponse:
        """
        Search the knowledge base and answer with the best article. When AI is enabled, the LLM
        rephrases that article using the top matches; if it fails, the article text is used as is.

        Nothing above the confidence threshold gives `found=False` and a fallback message offering
        to escalate; both fallback messages are in the bot language (the persisted `language` setting). `user_id` and `user_handle` are accepted but not used.
        """
        clean_query = query.strip()
        if not clean_query:
            return QueryResponse(
                query=query,
                found=False,
                confidence=0.0,
                answer=t("query_empty", await BotSettingsService.get_language(session)),
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
                answer=t("query_no_match", await BotSettingsService.get_language(session)),
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
