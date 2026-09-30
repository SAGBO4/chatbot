import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Tuple, Optional
import httpx
from app.config import settings
from app.models import KnowledgeArticle

logger = logging.getLogger(__name__)

# Sampling for the support answers: low temperature (stay close to the article), short replies.
AI_TEMPERATURE = 0.2
AI_MAX_OUTPUT_TOKENS = 500


@asynccontextmanager
async def _borrowed_client(client: Optional[httpx.AsyncClient]) -> AsyncIterator[httpx.AsyncClient]:
    """
    The caller's shared client if given, else a short-lived one.

    Only a client created here is closed: a caller-supplied one is shared and must outlive the call.
    """
    if client is not None:
        yield client
        return
    session = httpx.AsyncClient(timeout=10.0)
    try:
        yield session
    finally:
        await session.aclose()


class AIAssistantService:
    """
    Optional LLM step: turns the best knowledge base articles into an answer in the user's language.

    Providers: openai, gemini, deepseek (`DEFAULT_MODELS`). Any failure returns None so the
    caller falls back to the article text.
    """

    _shared_client: Optional[httpx.AsyncClient] = None

    @classmethod
    def set_shared_client(cls, client: Optional[httpx.AsyncClient]) -> None:
        """Configures a shared persistent httpx client for AI API calls."""
        cls._shared_client = client

    # How many of the best knowledge base articles the model is shown
    CONTEXT_ARTICLES = 3

    # Sane default model per provider, used when AI_MODEL is not set.
    DEFAULT_MODELS = {
        "openai": "gpt-4o-mini",
        "gemini": "gemini-2.5-flash",
        "deepseek": "deepseek-chat",
    }

    @staticmethod
    def _build_prompt(query: str, retrieved_articles: List[Tuple[KnowledgeArticle, float]]) -> str:
        """Prompt telling the model to answer only from the top 3 retrieved articles, in the question's language."""
        context_snippets = []
        for idx, (art, score) in enumerate(retrieved_articles[:AIAssistantService.CONTEXT_ARTICLES], start=1):
            context_snippets.append(f"[{idx}] Question: {art.question}\nSolution: {art.solution}")
        context_str = "\n\n".join(context_snippets)

        return (
            "You are a helpful, concise technical support assistant providing an official technical documentation excerpt for Stack Wallet. "
            "Never introduce yourself, never say 'I', 'in my opinion', 'as an assistant', or 'hope this helps'. "
            "Do NOT use conversational filler. Give only direct, objective, verified technical instructions step-by-step. "
            "Answer the user's question using ONLY the solutions provided below. "
            "Always answer in the same language as the user's question (French or English).\n\n"
            f"--- PROVIDED CONTEXT ---\n{context_str}\n\n"
            f"--- USER QUESTION ---\n{query}\n\n"
            "--- TECHNICAL RESOLUTION ---"
        )

    @classmethod
    async def generate_answer(
        cls,
        query: str,
        retrieved_articles: List[Tuple[KnowledgeArticle, float]],
        client: Optional[httpx.AsyncClient] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """Synthesize a context-grounded response using an LLM if enabled, or return None to bypass."""
        if not settings.AI_ENABLED or not settings.AI_API_KEY:
            return None

        if not retrieved_articles:
            return None

        effective_client = client or cls._shared_client
        prompt = user_prompt or cls._build_prompt(query, retrieved_articles)
        provider = (settings.AI_PROVIDER or "openai").strip().lower()
        model = settings.AI_MODEL or cls.DEFAULT_MODELS.get(provider, cls.DEFAULT_MODELS["openai"])

        try:
            if provider == "gemini":
                return await cls._call_gemini(prompt, model, effective_client, system_prompt=system_prompt)
            elif provider == "deepseek":
                return await cls._call_openai_compatible(
                    prompt, model, effective_client,
                    base_url="https://api.deepseek.com/chat/completions",
                    system_prompt=system_prompt,
                )
            elif provider == "openai":
                return await cls._call_openai_compatible(
                    prompt, model, effective_client,
                    base_url="https://api.openai.com/v1/chat/completions",
                    system_prompt=system_prompt,
                )
            else:
                logger.warning("Unknown AI_PROVIDER '%s', falling back to no AI answer.", provider)
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
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """Calls an OpenAI-compatible chat completions endpoint (used by OpenAI and DeepSeek)."""
        sys_msg = system_prompt or (
            "You are a helpful, concise support assistant. Always answer in the same "
            "language as the user's question (French or English)."
        )
        async with _borrowed_client(client) as session:
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
                            "content": sys_msg,
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": AI_TEMPERATURE,
                    "max_tokens": AI_MAX_OUTPUT_TOKENS,
                },
            )
            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    logger.warning("AI provider returned no choices: %s", data)
                    return None
                message = choices[0].get("message") or {}
                content = message.get("content")
                return content.strip() if content else None
            else:
                logger.warning("AI provider error %s: %s", response.status_code, response.text)
                return None

    @staticmethod
    async def _call_gemini(
        prompt: str,
        model: str,
        client: Optional[httpx.AsyncClient],
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """Calls the Google Gemini generateContent endpoint."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": settings.AI_API_KEY or "",
        }
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": AI_TEMPERATURE,
                "maxOutputTokens": AI_MAX_OUTPUT_TOKENS,
            },
        }
        if system_prompt:
            body["system_instruction"] = {"parts": [{"text": system_prompt}]}
        async with _borrowed_client(client) as session:
            response = await session.post(
                url,
                headers=headers,
                json=body,
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
