import logging
from typing import List, Tuple, Optional
import httpx
from backend.config import settings
from backend.models import KnowledgeArticle

logger = logging.getLogger(__name__)


class AIAssistantService:
    _shared_client: Optional[httpx.AsyncClient] = None

    @classmethod
    def set_shared_client(cls, client: Optional[httpx.AsyncClient]) -> None:
        """Configures a shared persistent httpx client for AI API calls."""
        cls._shared_client = client

    # Sane default model per provider, used when AI_MODEL is not set.
    DEFAULT_MODELS = {
        "openai": "gpt-4o-mini",
        "gemini": "gemini-2.5-flash",
        "deepseek": "deepseek-chat",
    }

    @staticmethod
    def _build_prompt(query: str, retrieved_articles: List[Tuple[KnowledgeArticle, float]]) -> str:
        context_snippets = []
        for idx, (art, score) in enumerate(retrieved_articles[:3], start=1):
            context_snippets.append(f"[{idx}] Question: {art.question}\nSolution: {art.solution}")
        context_str = "\n\n".join(context_snippets)

        return (
            "Tu es un assistant support technique bienveillant et concis. "
            "Réponds à la question de l'utilisateur en te basant UNIQUEMENT sur les solutions fournies ci-dessous. "
            "Réponds toujours dans la même langue que la question de l'utilisateur (français ou anglais).\n\n"
            f"--- CONTEXTE FOURNI ---\n{context_str}\n\n"
            f"--- QUESTION UTILISATEUR ---\n{query}\n\n"
            "--- RÉPONSE ---"
        )

    @classmethod
    async def generate_answer(
        cls,
        query: str,
        retrieved_articles: List[Tuple[KnowledgeArticle, float]],
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[str]:
        """Synthesize a context-grounded response using an LLM if enabled, or return None to bypass."""
        if not settings.AI_ENABLED or not settings.AI_API_KEY:
            return None

        if not retrieved_articles:
            return None

        effective_client = client or cls._shared_client
        prompt = cls._build_prompt(query, retrieved_articles)
        provider = (settings.AI_PROVIDER or "openai").strip().lower()
        model = settings.AI_MODEL or cls.DEFAULT_MODELS.get(provider, cls.DEFAULT_MODELS["openai"])

        try:
            if provider == "gemini":
                return await cls._call_gemini(prompt, model, effective_client)
            elif provider == "deepseek":
                return await cls._call_openai_compatible(
                    prompt, model, effective_client,
                    base_url="https://api.deepseek.com/chat/completions",
                )
            elif provider == "openai":
                return await cls._call_openai_compatible(
                    prompt, model, effective_client,
                    base_url="https://api.openai.com/v1/chat/completions",
                )
            else:
                logger.warning("Unknown AI_PROVIDER '%s', falling back to no AI answer.", provider)
                return None
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.error("Error communicating with AI provider '%s': %s", provider, exc)
            return None
        except Exception as exc:
            logger.error("Error communicating with AI provider '%s': %s", provider, exc)
            return None

    @staticmethod
    async def _call_openai_compatible(
        prompt: str,
        model: str,
        client: Optional[httpx.AsyncClient],
        base_url: str,
    ) -> Optional[str]:
        """Calls an OpenAI-compatible chat completions endpoint (used by OpenAI and DeepSeek)."""
        # A caller-supplied client is shared (connection pool, custom
        # transport) and must outlive this call, so only a client we create
        # ourselves gets closed via `async with`.
        owns_client = client is None
        session = client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await session.post(
                base_url,
                headers={
                    "Authorization": f"Bearer {settings.AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Tu es un assistant support utile et concis. Réponds toujours dans la "
                                "même langue que la question de l'utilisateur (français ou anglais)."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 500,
                },
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                logger.warning("AI provider error %s: %s", response.status_code, response.text)
                return None
        finally:
            if owns_client:
                await session.aclose()

    @staticmethod
    async def _call_gemini(
        prompt: str,
        model: str,
        client: Optional[httpx.AsyncClient],
    ) -> Optional[str]:
        """Calls the Google Gemini generateContent endpoint."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        # See _call_openai_compatible: only close a client we created ourselves.
        owns_client = client is None
        session = client or httpx.AsyncClient(timeout=10.0)
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": settings.AI_API_KEY or "",
        }
        try:
            response = await session.post(
                url,
                headers=headers,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 500,
                    },
                },
            )
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates") or []
                if not candidates:
                    logger.warning("Gemini returned no candidates: %s", data)
                    return None
                parts = candidates[0].get("content", {}).get("parts") or []
                if not parts:
                    logger.warning("Gemini returned no content parts: %s", data)
                    return None
                return parts[0]["text"].strip()
            else:
                logger.warning("AI provider error %s: %s", response.status_code, response.text)
                return None
        finally:
            if owns_client:
                await session.aclose()
