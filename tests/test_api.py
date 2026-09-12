import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.main import app
from backend.database import get_db, init_db
from backend.config import settings
from backend.models import Base, TicketStatus, KnowledgeArticle
from backend.services.knowledge_base import KnowledgeBaseService
from backend.services.ai_assistant import AIAssistantService


@pytest_asyncio.fixture
async def test_client(tmp_path):
    db_file = tmp_path / "api_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    await init_db(db_engine=engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_maker

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_query_endpoint_matching_and_fallback(test_client):
    client, session_maker = test_client

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
async def test_ai_assistant_pluggable_behavior():
    # 1. When AI is disabled, generate_answer returns None
    settings.AI_ENABLED = False
    article = KnowledgeArticle(question="Test question", solution="Test solution")
    ans_disabled = await AIAssistantService.generate_answer("Test query", [(article, 0.9)])
    assert ans_disabled is None

    # 2. When AI is enabled, mock LLM response
    settings.AI_ENABLED = True
    settings.AI_API_KEY = "mock_key"

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

    # Reset
    settings.AI_ENABLED = False


@pytest.mark.asyncio
async def test_ticket_lifecycle_and_feedback_loop(test_client):
    client, session_maker = test_client

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
