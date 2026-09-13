import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.config import settings
from backend.main import app
from backend.database import get_db, init_db
from backend.services.telegram_relay import TelegramRelay

TEST_BREVO_SECRET = "test-brevo-secret"
TEST_API_KEY = "test-api-key"


@pytest_asyncio.fixture
async def brevo_test_client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", TEST_API_KEY)

    db_file = tmp_path / "brevo_inbound_test.db"
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


async def create_ticket(client, user_id=999222, user_handle="brevo_user", question="Question test Brevo"):
    resp = await client.post(
        "/api/tickets",
        json={
            "user_id": user_id,
            "user_handle": user_handle,
            "question": question,
            "automated_answer": "Aucune idée",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_brevo_single_item_resolves_ticket_end_to_end(brevo_test_client, monkeypatch):
    monkeypatch.setattr(settings, "BREVO_INBOUND_SECRET", TEST_BREVO_SECRET)
    client, _ = brevo_test_client

    ticket_id = await create_ticket(client)

    mock_send_user = AsyncMock(return_value=True)
    mock_notify_group = AsyncMock(return_value=True)
    monkeypatch.setattr(TelegramRelay, "send_message_to_user", mock_send_user)
    monkeypatch.setattr(TelegramRelay, "notify_support_group", mock_notify_group)

    payload = {
        "items": [
            {
                "From": {"Address": "agent@company.com"},
                "Subject": f"Re: [Ticket #{ticket_id}] Nouvelle demande de support",
                "RawTextBody": "Voici la solution complète.\n\nOn 12/09/2026 wrote:\n> ...",
                "ExtractedMarkdownMessage": "Voici la solution complète.",
            }
        ]
    }
    resp = await client.post(
        f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_SECRET}", json=payload
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["status"] == "resolved"
    assert data["results"][0]["ticket_id"] == ticket_id

    mock_send_user.assert_called_once()
    assert mock_send_user.call_args[0][0] == 999222
    assert "Voici la solution complète." in mock_send_user.call_args[0][1]
    mock_notify_group.assert_called_once()

    # Knowledge base updated
    query_resp = await client.post("/api/query", json={"query": "Question test Brevo"})
    assert query_resp.status_code == 200
    assert "Voici la solution complète." in query_resp.json()["answer"]


@pytest.mark.asyncio
async def test_brevo_batch_partial_failure_does_not_block_other_items(brevo_test_client, monkeypatch):
    monkeypatch.setattr(settings, "BREVO_INBOUND_SECRET", TEST_BREVO_SECRET)
    client, _ = brevo_test_client

    ticket_id = await create_ticket(client, user_id=999333, question="Deuxième question")

    monkeypatch.setattr(TelegramRelay, "send_message_to_user", AsyncMock(return_value=True))
    monkeypatch.setattr(TelegramRelay, "notify_support_group", AsyncMock(return_value=True))

    payload = {
        "items": [
            {
                "From": {"Address": "agent@company.com"},
                "Subject": f"Re: [Ticket #{ticket_id}] Deuxième question",
                "RawTextBody": "Solution du deuxième ticket.",
                "ExtractedMarkdownMessage": None,
            },
            {
                "From": {"Address": "agent@company.com"},
                "Subject": "Re: pas de ticket ici",
                "RawTextBody": "Un message sans référence de ticket.",
                "ExtractedMarkdownMessage": None,
            },
        ]
    }
    resp = await client.post(
        f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_SECRET}", json=payload
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 2
    assert data["results"][0]["status"] == "resolved"
    assert data["results"][0]["ticket_id"] == ticket_id
    assert data["results"][1]["status"] == "no_ticket_reference"


@pytest.mark.asyncio
async def test_brevo_missing_token_rejected(brevo_test_client, monkeypatch):
    monkeypatch.setattr(settings, "BREVO_INBOUND_SECRET", TEST_BREVO_SECRET)
    client, _ = brevo_test_client

    payload = {
        "items": [
            {
                "From": {"Address": "attacker@evil.com"},
                "Subject": "Re: [Ticket #1]",
                "RawTextBody": "Forged solution",
            }
        ]
    }
    resp = await client.post("/api/webhooks/email-inbound/brevo", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_brevo_wrong_token_rejected(brevo_test_client, monkeypatch):
    monkeypatch.setattr(settings, "BREVO_INBOUND_SECRET", TEST_BREVO_SECRET)
    client, _ = brevo_test_client

    payload = {
        "items": [
            {
                "From": {"Address": "attacker@evil.com"},
                "Subject": "Re: [Ticket #1]",
                "RawTextBody": "Forged solution",
            }
        ]
    }
    resp = await client.post(
        "/api/webhooks/email-inbound/brevo?token=wrong-token", json=payload
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_brevo_unset_secret_rejected(brevo_test_client, monkeypatch):
    monkeypatch.setattr(settings, "BREVO_INBOUND_SECRET", None)
    client, _ = brevo_test_client

    payload = {
        "items": [
            {
                "From": {"Address": "attacker@evil.com"},
                "Subject": "Re: [Ticket #1]",
                "RawTextBody": "Forged solution",
            }
        ]
    }
    resp = await client.post(
        "/api/webhooks/email-inbound/brevo?token=anything", json=payload
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_brevo_item_with_raw_text_body_only_resolves(brevo_test_client, monkeypatch):
    monkeypatch.setattr(settings, "BREVO_INBOUND_SECRET", TEST_BREVO_SECRET)
    client, _ = brevo_test_client

    ticket_id = await create_ticket(client, user_id=999444, question="Question sans markdown")

    monkeypatch.setattr(TelegramRelay, "send_message_to_user", AsyncMock(return_value=True))
    monkeypatch.setattr(TelegramRelay, "notify_support_group", AsyncMock(return_value=True))

    payload = {
        "items": [
            {
                "From": {"Address": "agent@company.com"},
                "Subject": f"Re: [Ticket #{ticket_id}] Question sans markdown",
                "RawTextBody": "Solution en texte brut uniquement.",
            }
        ]
    }
    resp = await client.post(
        f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_SECRET}", json=payload
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"][0]["status"] == "resolved"
