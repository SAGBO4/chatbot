import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.main import app, clean_email_reply_body
from backend.database import get_db, init_db
from backend.models import TicketStatus
from backend.services.email_service import EmailService
from backend.services.telegram_relay import TelegramRelay


@pytest_asyncio.fixture
async def email_test_client(tmp_path):
    db_file = tmp_path / "email_sync_test.db"
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


def test_clean_email_reply_body():
    raw_email = (
        "Voici la solution : réinitialisez votre mot de passe.\n\n"
        "On 12/09/2026 at 15:00 support@example.com wrote:\n"
        "> [Ticket #10] Demande de support\n"
        "> Question..."
    )
    cleaned = clean_email_reply_body(raw_email)
    assert cleaned == "Voici la solution : réinitialisez votre mot de passe."


@pytest.mark.asyncio
async def test_email_inbound_resolution_and_race_condition(email_test_client, monkeypatch):
    client, session_maker = email_test_client

    # 1. Create a ticket
    create_resp = await client.post(
        "/api/tickets",
        json={
            "user_id": 999111,
            "user_handle": "samuel",
            "question": "Erreur SSL lors de la connexion",
            "automated_answer": "Aucune idée",
        },
    )
    assert create_resp.status_code == 201
    ticket_id = create_resp.json()["id"]

    # Mock Telegram relay
    mock_send_user = AsyncMock(return_value=True)
    mock_notify_group = AsyncMock(return_value=True)
    monkeypatch.setattr(TelegramRelay, "send_message_to_user", mock_send_user)
    monkeypatch.setattr(TelegramRelay, "notify_support_group", mock_notify_group)

    # 2. Support agent resolves ticket via Inbound Email
    email_webhook_payload = {
        "sender": "expert_network@company.com",
        "subject": f"Re: [Ticket #{ticket_id}] Nouvelle demande de support de @samuel",
        "body": "Installez les certificats racine CA à jour via update-ca-certificates.\n\nLe 12/09/2026 support a écrit :\n> ...",
    }
    inbound_resp = await client.post("/api/webhooks/email-inbound", json=email_webhook_payload)
    assert inbound_resp.status_code == 200
    inbound_data = inbound_resp.json()
    assert inbound_data["status"] == "resolved"
    assert inbound_data["channel"] == "EMAIL"

    # Verifies user received solution on Telegram
    mock_send_user.assert_called_once()
    assert mock_send_user.call_args[0][0] == 999111
    assert "update-ca-certificates" in mock_send_user.call_args[0][1]

    # Verifies support group informed of email resolution
    mock_notify_group.assert_called_once()
    assert f"Ticket #{ticket_id} résolu par Email" in mock_notify_group.call_args[0][0]

    # Verifies Knowledge Base updated: subsequent query finds it!
    query_resp = await client.post("/api/query", json={"query": "J'ai une erreur SSL à la connexion"})
    assert query_resp.status_code == 200
    assert "update-ca-certificates" in query_resp.json()["answer"]

    # 3. Race condition check: another agent tries to resolve on Telegram or Email
    second_email_resp = await client.post("/api/webhooks/email-inbound", json=email_webhook_payload)
    assert second_email_resp.status_code == 200
    assert second_email_resp.json()["status"] == "already_resolved"

    # Telegram resolution attempt also rejected safely
    tg_resolve_resp = await client.post(
        f"/api/tickets/{ticket_id}/resolve",
        json={
            "solution": "Autre solution tardive...",
            "resolved_by": "agent_tardif",
            "resolution_channel": "TELEGRAM",
        },
    )
    assert tg_resolve_resp.status_code == 200
    # The solution remains the first winning solution
    assert "update-ca-certificates" in tg_resolve_resp.json()["solution"]
    assert tg_resolve_resp.json()["resolution_channel"] == "EMAIL"
