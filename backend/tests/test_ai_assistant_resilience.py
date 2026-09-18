import pytest
from unittest.mock import AsyncMock
import httpx

from app.config import settings
from app.models import KnowledgeArticle
from app.services.ai_assistant import AIAssistantService


@pytest.fixture
def sample_article():
    return KnowledgeArticle(
        question="Comment réinitialiser mon mot de passe ?",
        solution="Cliquez sur 'Mot de passe oublié' sur l'écran de connexion.",
        keywords="mot de passe, reset, réinitialisation",
    )


@pytest.mark.asyncio
async def test_ai_assistant_timeout_handling(sample_article, monkeypatch):
    """Verifies that ReadTimeout and ConnectTimeout safely return None without unhandled errors."""
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "mock_key")
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ReadTimeout("Request timed out reading from server")

    result = await AIAssistantService.generate_answer(
        query="Mot de passe oublié",
        retrieved_articles=[(sample_article, 0.9)],
        client=mock_client,
    )
    assert result is None

    # Verify ConnectTimeout
    mock_client.post.side_effect = httpx.ConnectTimeout("Connection to OpenAI timed out")
    result_connect = await AIAssistantService.generate_answer(
        query="Mot de passe oublié",
        retrieved_articles=[(sample_article, 0.9)],
        client=mock_client,
    )
    assert result_connect is None


@pytest.mark.asyncio
async def test_ai_assistant_rate_limit_429(sample_article, monkeypatch):
    """Verifies that HTTP 429 (Rate Limit Exceeded) returns None without throwing."""
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "mock_key")
    monkeypatch.setattr(settings, "AI_PROVIDER", "deepseek")

    rate_limit_resp = httpx.Response(
        status_code=429,
        text='{"error": {"message": "Rate limit exceeded. Please retry later.", "type": "requests"}}',
    )
    mock_client = AsyncMock()
    mock_client.post.return_value = rate_limit_resp

    result = await AIAssistantService.generate_answer(
        query="Mot de passe oublié",
        retrieved_articles=[(sample_article, 0.9)],
        client=mock_client,
    )
    assert result is None


@pytest.mark.asyncio
async def test_ai_assistant_server_error_500(sample_article, monkeypatch):
    """Verifies that HTTP 500/503 from provider safely degrades to None."""
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "mock_key")
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")

    server_error_resp = httpx.Response(
        status_code=500,
        text='{"error": {"code": 500, "message": "Internal error encountered.", "status": "INTERNAL"}}',
    )
    mock_client = AsyncMock()
    mock_client.post.return_value = server_error_resp

    result = await AIAssistantService.generate_answer(
        query="Mot de passe oublié",
        retrieved_articles=[(sample_article, 0.9)],
        client=mock_client,
    )
    assert result is None


@pytest.mark.asyncio
async def test_ai_assistant_malformed_json_response(sample_article, monkeypatch):
    """Verifies handling when provider responds with empty or malformed JSON payloads."""
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "mock_key")

    # 1. OpenAI empty choices list
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    empty_choices_resp = httpx.Response(
        status_code=200,
        json={"choices": []},
    )
    mock_client = AsyncMock()
    mock_client.post.return_value = empty_choices_resp

    res_openai = await AIAssistantService.generate_answer(
        query="Mot de passe oublié",
        retrieved_articles=[(sample_article, 0.9)],
        client=mock_client,
    )
    assert res_openai is None

    # 2. Gemini empty candidates list
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    empty_candidates_resp = httpx.Response(
        status_code=200,
        json={"candidates": []},
    )
    mock_client.post.return_value = empty_candidates_resp

    res_gemini = await AIAssistantService.generate_answer(
        query="Mot de passe oublié",
        retrieved_articles=[(sample_article, 0.9)],
        client=mock_client,
    )
    assert res_gemini is None

    # 3. Gemini candidate with empty parts
    empty_parts_resp = httpx.Response(
        status_code=200,
        json={"candidates": [{"content": {"parts": []}}]},
    )
    mock_client.post.return_value = empty_parts_resp

    res_gemini_parts = await AIAssistantService.generate_answer(
        query="Mot de passe oublié",
        retrieved_articles=[(sample_article, 0.9)],
        client=mock_client,
    )
    assert res_gemini_parts is None


@pytest.mark.asyncio
async def test_ai_assistant_http_status_error(sample_article, monkeypatch):
    """Verifies that an unexpected HTTP network error is cleanly trapped."""
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "mock_key")
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ConnectError("Failed to establish a new connection")

    result = await AIAssistantService.generate_answer(
        query="Mot de passe oublié",
        retrieved_articles=[(sample_article, 0.9)],
        client=mock_client,
    )
    assert result is None
