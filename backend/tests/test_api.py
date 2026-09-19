import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import get_db, init_db
from app.config import settings
from app.models import Base, TicketStatus, KnowledgeArticle
from app.services.knowledge_base import KnowledgeBaseService
from app.services.ai_assistant import AIAssistantService

TEST_API_KEY = "test-api-key"


@pytest_asyncio.fixture
async def api_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", TEST_API_KEY)
    monkeypatch.setattr(settings, "AI_ENABLED", False)

    db_file = tmp_path / "api_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    await init_db(db_engine=engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-API-Key": TEST_API_KEY}
    ) as client:
        yield client, session_maker

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_query_endpoint_matching_and_fallback(api_env):
    client, session_maker = api_env

    # Pre-populate knowledge base
    async with session_maker() as session:
        await KnowledgeBaseService.add_article(
            session=session,
            question="Comment changer son adresse email ?",
            solution="Allez dans Paramètres > Profil > Modifier l'adresse email.",
            keywords="email, adresse, profil, changer",
        )

    # 1. Query with matching question
    resp = await client.post("/api/query", json={"query": "Je voudrais changer mon adresse email"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["confidence"] > 0.3
    assert "Paramètres > Profil" in data["answer"]
    assert data["requires_resolution_confirmation"] is True

    # 2. Query with no match (fallback)
    fallback_resp = await client.post("/api/query", json={"query": "Quelle est la distance jusqu'à la lune ?"})
    assert fallback_resp.status_code == 200
    fb_data = fallback_resp.json()
    assert fb_data["found"] is False
    assert fb_data["confidence"] == 0.0
    assert "équipe support" in fb_data["answer"]


@pytest.mark.asyncio
async def test_ai_assistant_pluggable_behavior(monkeypatch):
    # 1. When AI is disabled, generate_answer returns None
    monkeypatch.setattr(settings, "AI_ENABLED", False)
    article = KnowledgeArticle(question="Test question", solution="Test solution")
    ans_disabled = await AIAssistantService.generate_answer("Test query", [(article, 0.9)])
    assert ans_disabled is None

    # 2. When AI is enabled, mock LLM response
    # AI_PROVIDER/AI_MODEL are pinned explicitly here (rather than relying on
    # class defaults) so this test is unaffected by whatever a developer has
    # configured in their local .env (e.g. AI_PROVIDER=gemini).
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "mock_key")
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    monkeypatch.setattr(settings, "AI_MODEL", None)

    mock_resp = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": "Solution synthétisée par l'IA."}}]},
    )

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    ans_enabled = await AIAssistantService.generate_answer(
        "Test query", [(article, 0.9)], client=mock_client
    )
    assert ans_enabled == "Solution synthétisée par l'IA."


@pytest.mark.asyncio
async def test_ai_assistant_deepseek_provider(monkeypatch):
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "mock_deepseek_key")
    monkeypatch.setattr(settings, "AI_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "AI_MODEL", None)

    article = KnowledgeArticle(question="Test question", solution="Test solution")

    mock_resp = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": "Réponse DeepSeek."}}]},
    )
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    answer = await AIAssistantService.generate_answer(
        "Test query", [(article, 0.9)], client=mock_client
    )
    assert answer == "Réponse DeepSeek."
    call_url = mock_client.post.call_args[0][0]
    assert "deepseek.com" in call_url


@pytest.mark.asyncio
async def test_ai_assistant_gemini_provider(monkeypatch):
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "mock_gemini_key")
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_MODEL", None)

    article = KnowledgeArticle(question="Test question", solution="Test solution")

    mock_resp = httpx.Response(
        status_code=200,
        json={
            "candidates": [
                {"content": {"parts": [{"text": "Réponse Gemini."}]}}
            ]
        },
    )
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    answer = await AIAssistantService.generate_answer(
        "Test query", [(article, 0.9)], client=mock_client
    )
    assert answer == "Réponse Gemini."
    call_url = mock_client.post.call_args[0][0]
    assert "generativelanguage.googleapis.com" in call_url
    assert "gemini-2.5-flash" in call_url  # default model used since AI_MODEL unset

    # Reset
    settings.AI_ENABLED = False


@pytest.mark.asyncio
async def test_ticket_lifecycle_and_feedback_loop(api_env):
    client, session_maker = api_env

    # 1. Create ticket
    create_resp = await client.post(
        "/api/tickets",
        json={
            "user_id": 987654321,
            "user_handle": "alice",
            "question": "Impossible d'exporter mon rapport au format PDF",
            "automated_answer": "Aucune solution trouvée.",
        },
    )
    assert create_resp.status_code == 201
    ticket = create_resp.json()
    ticket_id = ticket["id"]
    assert ticket["status"] == TicketStatus.OPEN.value
    assert ticket["user_id"] == 987654321

    # 2. Get ticket by ID
    get_resp = await client.get(f"/api/tickets/{ticket_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["question"] == "Impossible d'exporter mon rapport au format PDF"

    # 3. Resolve ticket (with automated knowledge base ingestion)
    resolve_resp = await client.post(
        f"/api/tickets/{ticket_id}/resolve",
        json={
            "solution": "Activez les popups dans votre navigateur puis réessayez l'export.",
            "resolved_by": "support_agent_bob",
            "add_to_knowledge_base": True,
        },
    )
    assert resolve_resp.status_code == 200
    res_data = resolve_resp.json()
    assert res_data["status"] == TicketStatus.RESOLVED.value
    assert res_data["solution"] == "Activez les popups dans votre navigateur puis réessayez l'export."
    assert res_data["resolved_by"] == "support_agent_bob"

    # 4. Verify feedback loop: Knowledge base now contains the solution and answers immediately!
    query_resp = await client.post(
        "/api/query",
        json={"query": "Mon export PDF ne fonctionne pas du tout"},
    )
    assert query_resp.status_code == 200
    q_data = query_resp.json()
    assert q_data["found"] is True
    assert "Activez les popups" in q_data["answer"]


@pytest.mark.asyncio
async def test_api_rejects_missing_or_invalid_key(api_env):
    client, _ = api_env

    # No X-API-Key header at all
    resp_no_key = await client.post(
        "/api/query", json={"query": "test"}, headers={"X-API-Key": ""}
    )
    assert resp_no_key.status_code == 401

    # Wrong X-API-Key
    resp_wrong_key = await client.post(
        "/api/query", json={"query": "test"}, headers={"X-API-Key": "wrong-key"}
    )
    assert resp_wrong_key.status_code == 401


@pytest.mark.asyncio
async def test_api_rejected_when_key_not_configured(api_env, monkeypatch):
    client, _ = api_env
    monkeypatch.setattr(settings, "API_KEY", None)

    resp = await client.post("/api/query", json={"query": "test"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_support_card_attach_and_lookup_round_trip(api_env):
    client, _ = api_env

    create_resp = await client.post(
        "/api/tickets",
        json={
            "user_id": 111222333,
            "user_handle": "diane",
            "question": "Le bouton d'export ne répond plus",
            "automated_answer": None,
        },
    )
    assert create_resp.status_code == 201
    ticket_id = create_resp.json()["id"]

    # Attach the support-group card's Telegram message id
    attach_resp = await client.post(
        f"/api/tickets/{ticket_id}/support-card",
        json={"message_id": 4242},
    )
    assert attach_resp.status_code == 200
    assert attach_resp.json()["support_group_message_id"] == 4242

    # Look it back up by that message id
    lookup_resp = await client.get("/api/tickets/by-support-message/4242")
    assert lookup_resp.status_code == 200
    assert lookup_resp.json()["id"] == ticket_id


@pytest.mark.asyncio
async def test_support_card_attach_on_unknown_ticket_returns_404(api_env):
    client, _ = api_env

    resp = await client.post("/api/tickets/999999/support-card", json={"message_id": 1})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_support_card_lookup_unknown_message_returns_404(api_env):
    client, _ = api_env

    resp = await client.get("/api/tickets/by-support-message/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_check_endpoint(api_env):
    client, _ = api_env
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["service"] == "support-bot-backend"


@pytest.mark.asyncio
async def test_list_tickets_status_filter_and_validation(api_env):
    client, _ = api_env
    # Create an open ticket
    await client.post(
        "/api/tickets",
        json={
            "user_id": 999,
            "user_handle": "alice",
            "question": "Status filter test question",
            "automated_answer": None,
        },
    )

    # Valid filter: open (case-insensitive)
    resp_open = await client.get("/api/tickets?status_filter=open")
    assert resp_open.status_code == 200
    assert len(resp_open.json()) >= 1
    assert all(t["status"] == TicketStatus.OPEN.value for t in resp_open.json())

    # Valid filter: OPEN (uppercase)
    resp_open_upper = await client.get("/api/tickets?status_filter=OPEN")
    assert resp_open_upper.status_code == 200
    assert len(resp_open_upper.json()) >= 1

    # Valid filter: resolved (should be empty for our new ticket)
    resp_resolved = await client.get("/api/tickets?status_filter=resolved")
    assert resp_resolved.status_code == 200


    # Invalid filter: should be rejected by FastAPI / Pydantic with 422 Unprocessable Entity
    resp_invalid = await client.get("/api/tickets?status_filter=non_existent_status")
    assert resp_invalid.status_code == 422


@pytest.mark.asyncio
async def test_list_knowledge_pagination(api_env):
    client, _ = api_env
    # Query knowledge with pagination
    resp = await client.get("/api/knowledge?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 2



@pytest.mark.asyncio
async def test_openapi_version_comes_from_the_package(api_env):
    import app

    client, _ = api_env
    response = await client.get("/openapi.json")

    assert response.json()["info"]["version"] == app.__version__ == "1.1.0"
