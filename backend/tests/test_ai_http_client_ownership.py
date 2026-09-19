"""AIAssistantService closes an HTTP client only if it created it: a shared one must outlive the call."""
import httpx
import pytest

from app.config import settings
from app.services import ai_assistant
from app.services.ai_assistant import AIAssistantService


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_a_shared_client_is_left_open(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_KEY", "k")
    shared = _client(lambda request: httpx.Response(200, json={"choices": [{"message": {"content": " hi "}}]}))

    answer = await AIAssistantService._call_openai_compatible("q", "m", shared, "https://ai.test/v1/chat")

    assert answer == "hi"
    assert not shared.is_closed
    await shared.aclose()


@pytest.mark.asyncio
async def test_gemini_reads_the_first_part_and_leaves_a_shared_client_open(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_KEY", "k")
    body = {"candidates": [{"content": {"parts": [{"text": " bonjour "}]}}]}
    shared = _client(lambda request: httpx.Response(200, json=body))

    answer = await AIAssistantService._call_gemini("q", "gemini-x", shared)

    assert answer == "bonjour"
    assert not shared.is_closed
    await shared.aclose()


@pytest.mark.asyncio
async def test_a_client_created_for_the_call_is_closed_even_when_the_call_fails(monkeypatch):
    created = []

    class Recording(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            super().__init__(transport=httpx.MockTransport(self._boom), timeout=kwargs.get("timeout"))
            created.append(self)

        @staticmethod
        def _boom(request):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(ai_assistant.httpx, "AsyncClient", Recording)

    with pytest.raises(httpx.ConnectError):
        await AIAssistantService._call_openai_compatible("q", "m", None, "https://ai.test/v1/chat")

    assert len(created) == 1 and created[0].is_closed
