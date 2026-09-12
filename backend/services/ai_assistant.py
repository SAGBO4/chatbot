import logging
from typing import List, Tuple, Optional
import httpx
from backend.config import settings
from backend.models import KnowledgeArticle

logger = logging.getLogger(__name__)


class AIAssistantService:
    @staticmethod
    async def generate_answer(
        query: str,
        retrieved_articles: List[Tuple[KnowledgeArticle, float]],
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[str]:
        """Synthesize a context-grounded response using an LLM if enabled, or return None to bypass."""
        if not settings.AI_ENABLED or not settings.AI_API_KEY:
            return None

        if not retrieved_articles:
            return None

        # Build context from top articles
        context_snippets = []
        for idx, (art, score) in enumerate(retrieved_articles[:3], start=1):
            context_snippets.append(f"[{idx}] Question: {art.question}\nSolution: {art.solution}")
        context_str = "\n\n".join(context_snippets)

        prompt = (
            "Tu es un assistant support technique bienveillant et concis. "
            "Réponds à la question de l'utilisateur en te basant UNIQUEMENT sur les solutions fournies ci-dessous.\n\n"
            f"--- CONTEXTE FOURNI ---\n{context_str}\n\n"
            f"--- QUESTION UTILISATEUR ---\n{query}\n\n"
            "--- RÉPONSE ---"
        )

        try:
            http_client = client or httpx.AsyncClient(timeout=10.0)
            async with http_client as session:
                # Compatible with OpenAI-compatible chat completion endpoints
                response = await session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.AI_MODEL,
                        "messages": [
                            {"role": "system", "content": "Tu es un assistant support utile et concis."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.2,
                        "max_tokens": 500,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    answer = data["choices"][0]["message"]["content"].strip()
                    return answer
                else:
                    logger.warning("AI provider error %s: %s", response.status_code, response.text)
                    return None
        except Exception as exc:
            logger.error("Error communicating with AI provider: %s", exc)
            return None
