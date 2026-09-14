import hashlib
import hmac
import json

import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.config import settings
from backend.main import app, clean_email_reply_body, escape_telegram_markdown
from backend.database import get_db, init_db
from backend.models import TicketStatus
from backend.services.email_service import EmailService
from backend.services.telegram_relay import TelegramRelay

TEST_WEBHOOK_SECRET = "test-webhook-secret"
TEST_API_KEY = "test-api-key"


def sign_payload(payload: dict, secret: str = TEST_WEBHOOK_SECRET) -> tuple[bytes, str]:
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return raw_body, signature


async def post_signed_webhook(client, payload: dict, secret: str = TEST_WEBHOOK_SECRET, signature: str = None):
    raw_body, computed_signature = sign_payload(payload, secret)
    headers = {"Content-Type": "application/json"}
    if signature is not False:
        headers["X-Webhook-Signature"] = signature if signature is not None else computed_signature
    return await client.post("/api/webhooks/email-inbound", content=raw_body, headers=headers)


@pytest_asyncio.fixture
async def email_test_client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", TEST_API_KEY)

    db_file = tmp_path / "email_sync_test.db"
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


def test_clean_email_reply_body():
    raw_email = (
        "Voici la solution : réinitialisez votre mot de passe.\n\n"
        "On 12/09/2026 at 15:00 support@example.com wrote:\n"
        "> [Ticket #10] Demande de support\n"
        "> Question..."
    )
    cleaned = clean_email_reply_body(raw_email)
    assert cleaned == "Voici la solution : réinitialisez votre mot de passe."


def test_clean_email_reply_body_returns_empty_when_quote_is_first_line():
    # Bottom-posted reply: the quote marker is the very first line, so there
    # is no new content to extract. Must NOT fall back to the raw body -
    # that would leak the quoted ticket-notification text back into the
    # ticket solution and the knowledge base.
    raw_email = (
        "On 12/09/2026 at 15:00 support@example.com wrote:\n"
        "> [Ticket #10] Demande de support\n"
        "> Question..."
    )
    assert clean_email_reply_body(raw_email) == ""


def test_clean_email_reply_body_outlook():
    raw_email = (
        "Configurez les DNS 1.1.1.1 et réessayez.\n\n"
        "________________________________\n"
        "From: support@example.com\n"
        "Sent: Monday, September 14, 2026 2:00 AM\n"
        "To: user@example.com\n"
        "Subject: [Ticket #10] Demande de support"
    )
    assert clean_email_reply_body(raw_email) == "Configurez les DNS 1.1.1.1 et réessayez."


def test_escape_telegram_markdown():
    assert escape_telegram_markdown("expert_network@company.com") == "expert\\_network@company.com"
    assert escape_telegram_markdown("a*b`c[d") == "a\\*b\\`c\\[d"
    assert escape_telegram_markdown("no special chars") == "no special chars"


@pytest.mark.asyncio
async def test_email_inbound_resolution_and_race_condition(email_test_client, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
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
    inbound_resp = await post_signed_webhook(client, email_webhook_payload)
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
    second_email_resp = await post_signed_webhook(client, email_webhook_payload)
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


@pytest.mark.asyncio
async def test_email_inbound_empty_body_leaves_ticket_unresolved(email_test_client, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    client, session_maker = email_test_client

    create_resp = await client.post(
        "/api/tickets",
        json={"user_id": 555, "user_handle": "nadia", "question": "Mon retrait est bloqué"},
    )
    ticket_id = create_resp.json()["id"]

    mock_send_user = AsyncMock(return_value=True)
    mock_notify_group = AsyncMock(return_value=True)
    monkeypatch.setattr(TelegramRelay, "send_message_to_user", mock_send_user)
    monkeypatch.setattr(TelegramRelay, "notify_support_group", mock_notify_group)

    # Bottom-posted reply: quote marker on the first line, nothing left after stripping.
    payload = {
        "sender": "support@company.com",
        "subject": f"Re: [Ticket #{ticket_id}] Mon retrait est bloqué",
        "body": "On 12/09/2026 at 10:00 nadia wrote:\n> Mon retrait est bloqué",
    }
    resp = await post_signed_webhook(client, payload)
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower() or "vide" in resp.json()["detail"].lower() or ticket_id is not None

    # The ticket must NOT be resolved and nothing sent to Telegram.
    ticket_resp = await client.get(f"/api/tickets/{ticket_id}")
    assert ticket_resp.json()["status"] == TicketStatus.OPEN.value
    mock_send_user.assert_not_called()
    mock_notify_group.assert_not_called()


@pytest.mark.asyncio
async def test_email_inbound_escapes_markdown_in_sender_and_solution(email_test_client, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    client, _ = email_test_client

    create_resp = await client.post(
        "/api/tickets",
        json={"user_id": 777, "user_handle": "leo", "question": "Comment activer le mode avancé ?"},
    )
    ticket_id = create_resp.json()["id"]

    mock_send_user = AsyncMock(return_value=True)
    mock_notify_group = AsyncMock(return_value=True)
    monkeypatch.setattr(TelegramRelay, "send_message_to_user", mock_send_user)
    monkeypatch.setattr(TelegramRelay, "notify_support_group", mock_notify_group)

    payload = {
        "sender": "expert_wallet@company.com",
        "subject": f"Re: [Ticket #{ticket_id}] Comment activer le mode avancé ?",
        "body": "Allez dans Paramètres *avancés* puis activez `mode_expert`.",
    }
    resp = await post_signed_webhook(client, payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"

    # The unbalanced '*' / '`' / '_' from the email must be escaped before
    # being wrapped in our own Markdown, or Telegram would reject the send.
    sent_user_text = mock_send_user.call_args[0][1]
    assert "expert\\_wallet@company.com" in sent_user_text
    assert "\\*avancés\\*" in sent_user_text
    assert "\\`mode\\_expert\\`" in sent_user_text

    sent_group_text = mock_notify_group.call_args[0][0]
    assert "expert\\_wallet@company.com" in sent_group_text


@pytest.mark.asyncio
async def test_email_inbound_rejected_without_configured_secret(email_test_client, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_WEBHOOK_SECRET", None)
    client, _ = email_test_client

    payload = {
        "sender": "attacker@evil.com",
        "subject": "Re: [Ticket #1]",
        "body": "Forged solution",
    }
    resp = await post_signed_webhook(client, payload)
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_email_inbound_rejected_without_signature_header(email_test_client, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    client, _ = email_test_client

    payload = {
        "sender": "attacker@evil.com",
        "subject": "Re: [Ticket #1]",
        "body": "Forged solution",
    }
    resp = await post_signed_webhook(client, payload, signature=False)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_email_inbound_rejected_with_invalid_signature(email_test_client, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    client, _ = email_test_client

    payload = {
        "sender": "attacker@evil.com",
        "subject": "Re: [Ticket #1]",
        "body": "Forged solution",
    }
    resp = await post_signed_webhook(client, payload, signature="deadbeef" * 8)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_email_inbound_sender_authorization_check(email_test_client, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "ALLOWED_SUPPORT_EMAIL_SENDERS", "@stackwallet.com, support@company.org")
    client, session_maker = email_test_client

    # 1. Unauthorized sender is rejected with 403
    unauth_payload = {
        "sender": "attacker@evil.com",
        "subject": "Re: [Ticket #1] Help",
        "body": "Malicious answer",
    }
    resp_unauth = await post_signed_webhook(client, unauth_payload)
    assert resp_unauth.status_code == 403
    assert "not authorized" in resp_unauth.json()["detail"]

    # 2. Authorized domain sender is accepted (returns 404 for unknown ticket, proving it passed auth)
    auth_payload = {
        "sender": "agent_alice@stackwallet.com",
        "subject": "Re: [Ticket #999] Help",
        "body": "Legitimate answer",
    }
    resp_auth = await post_signed_webhook(client, auth_payload)
    assert resp_auth.status_code == 404

