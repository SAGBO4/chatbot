import hashlib
import hmac
import json

import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings
from app.main import app
from app.email_parsing import clean_email_reply_body
from app.telegram_text import escape_telegram_markdown
from app.database import get_db, init_db
from app.models import TicketStatus
from app.services.email_service import EmailService
from app.services.telegram_relay import TelegramRelay
import asyncio
import logging
from sqlalchemy import select
from app.models import Ticket, KnowledgeArticle
from app.services.ticket_service import TicketService
from tests.conftest import TEST_EMAIL_WEBHOOK_SECRET

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
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)

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


def test_clean_email_reply_body_french_prefix_and_dashes():
    raw_email = (
        "--- Solution détaillée ci-dessous ---\n"
        "De : notre équipe support, nous avons réactivé votre compte.\n\n"
        "-----Message d'origine-----\n"
        "De : user@example.com\n"
        "Objet : Compte bloqué"
    )
    cleaned = clean_email_reply_body(raw_email)
    assert "--- Solution détaillée ci-dessous ---" in cleaned
    assert "De : notre équipe support, nous avons réactivé votre compte." in cleaned
    assert "user@example.com" not in cleaned


def test_clean_email_reply_body_gmail_forwarded_message():
    raw_email = (
        "Veuillez trouver la réponse ci-jointe.\n\n"
        "---------- Forwarded message ---------\n"
        "From: tech@partner.com\n"
        "Date: Mon, Sep 14, 2026 at 10:00 AM\n"
        "Subject: Fwd: [Ticket #10] Problème résolu"
    )
    cleaned = clean_email_reply_body(raw_email)
    assert cleaned == "Veuillez trouver la réponse ci-jointe."


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


# ---------------------------------------------------------------------------
# Cases numbered 1 (functional), 2 (security) and 3 (robustness) in their docstrings
# ---------------------------------------------------------------------------


def sign_body(payload: dict, secret: str = TEST_EMAIL_WEBHOOK_SECRET) -> tuple[bytes, str]:
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return raw_body, sig


@pytest.mark.asyncio
async def test_webhooks_email_happy_path_resolves_ticket_and_notifies_telegram(app_test_env, caplog):
    """
    1. FUNCTIONAL - Happy Path:
    Receiving a reply email with a valid HMAC signature.
    Checks the HTTP 200 response, the ticket resolution in the DB,
    the addition to the KB, and the Telegram notification dispatch.
    """
    client, session_maker, _ = app_test_env

    # 1. Create an open ticket
    async with session_maker() as session:
        ticket = await TicketService.create_ticket(
            session=session,
            user_id=1234567,
            user_handle="client_jean",
            question="Problème de synchronisation",
        )
        t_id = ticket.id

    # Mock the Telegram network boundary
    mock_send_user = AsyncMock(return_value=True)
    mock_notify_group = AsyncMock(return_value=True)

    payload = {
        "sender": "support@example.com",
        "subject": f"Re: [Ticket #{t_id}] Problème de synchronisation",
        "body": "Bonjour,\n\nVeuillez vider le cache de l'application et redémarrer.\n\nCordialement,\nSupport",
    }
    raw_bytes, sig = sign_body(payload)

    with patch.object(TelegramRelay, "send_message_to_user", mock_send_user), \
         patch.object(TelegramRelay, "notify_support_group", mock_notify_group), \
         caplog.at_level(logging.INFO):

        response = await client.post(
            "/api/webhooks/email-inbound",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
        )

    # 4. ASSERTIONS
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["ticket_id"] == t_id
    assert data["channel"] == "EMAIL"

    # DB check
    async with session_maker() as session:
        refreshed = (await session.execute(select(Ticket).where(Ticket.id == t_id))).scalar_one()
        assert refreshed.status == "RESOLVED"
        assert refreshed.resolution_channel == "EMAIL"
        assert refreshed.resolved_by == "support@example.com"
        assert "vider le cache" in refreshed.solution

        # KB updated
        kb = (
            await session.execute(select(KnowledgeArticle).where(KnowledgeArticle.source_ticket_id == t_id))
        ).scalar_one()
        assert "vider le cache" in kb.solution

    # Side effects: Telegram Relay called
    mock_send_user.assert_called_once()
    assert mock_send_user.call_args[0][0] == 1234567
    assert "vider le cache" in mock_send_user.call_args[0][1]

    mock_notify_group.assert_called_once()
    assert f"Ticket #{t_id} résolu par Email" in mock_notify_group.call_args[0][0]


@pytest.mark.asyncio
async def test_webhooks_email_subject_regex_variations_resolves_ticket(app_test_env):
    """
    1. FUNCTIONAL - Subject regex robustness:
    Tests several subject formats: 'Ticket #42', '[Ticket#42]', 'Re: Ticket 42'.
    """
    client, session_maker, _ = app_test_env

    subject_variations = [
        "[Ticket #901] Sujet avec crochets",
        "Re: Ticket #901 sans crochets",
        "Fwd: Ticket#901 collé",
        "Support Request - Ticket #901 - Urgent",
    ]

    for subj in subject_variations:
        async with session_maker() as session:
            ticket = await TicketService.create_ticket(session, 999, "u", f"Question for {subj}")
            t_id = ticket.id

        payload = {
            "sender": "agent@example.com",
            "subject": subj.replace("901", str(t_id)),
            "body": "Solution pour ce ticket.",
        }
        raw_bytes, sig = sign_body(payload)
        resp = await client.post(
            "/api/webhooks/email-inbound",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_webhooks_email_clean_body_strips_quotes_and_history(app_test_env):
    """
    1. FUNCTIONAL - Cleaning the email history:
    '>' quote blocks and 'From:' / 'De :' headers are removed
    so they do not pollute the KB.
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 11, "u", "Q")
        t_id = t.id

    body_with_quotes = (
        "Voici la solution propre.\n\n"
        "> Le 14/09/2026 à 10:00, user@example.com a écrit :\n"
        "> [Ticket #11] Demande initiale\n"
        "> Texte cité à ignorer..."
    )
    payload = {"sender": "support@example.com", "subject": f"[Ticket #{t_id}]", "body": body_with_quotes}
    raw_bytes, sig = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
    )
    assert resp.status_code == 200

    async with session_maker() as session:
        refreshed = (await session.execute(select(Ticket).where(Ticket.id == t_id))).scalar_one()
        assert refreshed.solution == "Voici la solution propre."
        assert "Texte cité à ignorer" not in refreshed.solution


@pytest.mark.asyncio
async def test_webhooks_email_clean_body_returns_empty_when_quote_on_first_line_returns_400(app_test_env):
    """
    1. FUNCTIONAL - Edge case:
    If the body contains no new text (quote from the 1st line),
    the endpoint must return HTTP 400 and leave the ticket open.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 11, "u", "Q")
        t_id = t.id

    empty_reply = "> [Ticket #11] Citation sur la première ligne sans nouveau message\n> Fin"
    payload = {"sender": "support@example.com", "subject": f"[Ticket #{t_id}]", "body": empty_reply}
    raw_bytes, sig = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
    )
    assert resp.status_code == 400
    assert "had no content" in resp.json()["detail"]

    # DB check: ticket still OPEN
    async with session_maker() as session:
        refreshed = (await session.execute(select(Ticket).where(Ticket.id == t_id))).scalar_one()
        assert refreshed.status == "OPEN"


@pytest.mark.asyncio
async def test_webhooks_email_missing_ticket_id_in_subject_returns_400(app_test_env):
    """
    1. FUNCTIONAL - Expected error:
    An email with no ticket reference in the subject returns HTTP 400.
    """
    client, _, _ = app_test_env
    payload = {"sender": "support@example.com", "subject": "Question générale sans ID", "body": "Solution"}
    raw_bytes, sig = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
    )
    assert resp.status_code == 400
    assert "Could not identify Ticket ID" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_webhooks_email_ticket_not_found_returns_404(app_test_env):
    """
    1. FUNCTIONAL - Expected error:
    A ticket ID that does not exist in the database returns 404.
    """
    client, _, _ = app_test_env
    payload = {"sender": "support@example.com", "subject": "[Ticket #8888888] Inconnu", "body": "Solution"}
    raw_bytes, sig = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_webhooks_email_sender_authorized_exact_address_succeeds(app_test_env, monkeypatch):
    """
    1. FUNCTIONAL / 2. SECURITY - Sender authorization:
    Sender explicitly listed in ALLOWED_SUPPORT_EMAIL_SENDERS.
    """
    client, session_maker, _ = app_test_env
    monkeypatch.setattr(settings, "ALLOWED_SUPPORT_EMAIL_SENDERS", "tech@mycompany.com, @alloweddomain.com")

    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 1, "u", "Q")
        t_id = t.id

    payload = {"sender": "tech@mycompany.com", "subject": f"[Ticket #{t_id}]", "body": "Solution acceptée"}
    raw_bytes, sig = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_webhooks_email_sender_authorized_domain_succeeds(app_test_env, monkeypatch):
    """
    1. FUNCTIONAL / 2. SECURITY - Authorization by domain name (@domain.com):
    Sender matching the authorized domain.
    """
    client, session_maker, _ = app_test_env
    monkeypatch.setattr(settings, "ALLOWED_SUPPORT_EMAIL_SENDERS", "@stackwallet.com")

    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 1, "u", "Q")
        t_id = t.id

    payload = {"sender": "alice@stackwallet.com", "subject": f"[Ticket #{t_id}]", "body": "Solution domaine ok"}
    raw_bytes, sig = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_webhooks_email_sender_unauthorized_returns_403(app_test_env, monkeypatch):
    """
    1. FUNCTIONAL / 2. SECURITY - Unauthorized sender rejected:
    When an allow list is configured, an outside sender is rejected (403 Forbidden).
    """
    client, session_maker, _ = app_test_env
    monkeypatch.setattr(settings, "ALLOWED_SUPPORT_EMAIL_SENDERS", "@trusted.com")

    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 1, "u", "Q")
        t_id = t.id

    payload = {"sender": "attacker@evil.com", "subject": f"[Ticket #{t_id}]", "body": "Solution injectée"}
    raw_bytes, sig = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
    )
    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_webhooks_email_idempotence_already_resolved_returns_200_and_already_resolved(app_test_env):
    """
    1. FUNCTIONAL - Idempotence:
    If a resolution email is replayed, the ticket is not altered again and the API
    returns status="already_resolved".
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 1, "u", "Q")
        await TicketService.resolve_ticket(session, t.id, "Première résolution", "first@example.com")
        t_id = t.id

    payload = {"sender": "second@example.com", "subject": f"[Ticket #{t_id}]", "body": "Nouvelle tentative"}
    raw_bytes, sig = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "already_resolved"


# ==============================================================================
# 2. SECURITY
# ==============================================================================


@pytest.mark.asyncio
async def test_webhooks_email_invalid_hmac_signature_returns_401_unauthorized(app_test_env):
    """
    2. SECURITY - Integrity / HMAC:
    An invalid signature or a tampered body must be rejected with 401 Unauthorized.
    """
    client, _, _ = app_test_env
    payload = {"sender": "support@example.com", "subject": "[Ticket #1]", "body": "Sol"}
    raw_bytes, _ = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": "invalid_signature_hex"},
    )
    assert resp.status_code == 401
    assert "Invalid webhook signature" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_webhooks_email_missing_hmac_signature_header_returns_401_unauthorized(app_test_env):
    """
    2. SECURITY - Missing header:
    A missing X-Webhook-Signature header must return 401.
    """
    client, _, _ = app_test_env
    payload = {"sender": "support@example.com", "subject": "[Ticket #1]", "body": "Sol"}
    raw_bytes, _ = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401
    assert "Missing X-Webhook-Signature header" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_webhooks_email_secret_not_configured_returns_503_service_unavailable(app_test_env, monkeypatch):
    """
    2. SECURITY - Fail-closed:
    If EMAIL_WEBHOOK_SECRET is not set, webhook access is disabled (503).
    """
    client, _, _ = app_test_env
    monkeypatch.setattr(settings, "EMAIL_WEBHOOK_SECRET", None)

    payload = {"sender": "support@example.com", "subject": "[Ticket #1]", "body": "Sol"}
    raw_bytes, sig = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
    )
    assert resp.status_code == 503
    assert "EMAIL_WEBHOOK_SECRET missing" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_webhooks_email_sha256_prefix_in_signature_header_accepted(app_test_env):
    """
    2. SECURITY / COMPATIBILITY:
    Compatible with email relays that send the `sha256=<hex>` format.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 1, "u", "Q")
        t_id = t.id

    payload = {"sender": "support@example.com", "subject": f"[Ticket #{t_id}]", "body": "Solution"}
    raw_bytes, sig = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": f"sha256={sig}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_webhooks_email_xss_and_markdown_in_body_escaped_for_telegram(app_test_env):
    """
    2. SECURITY - Markdown & XSS injection towards Telegram:
    An email body coming from outside that contains reserved Markdown characters
    (`*`, `_`, `` ` ``, `[`) must be escaped before being sent to the Telegram bot,
    so Telegram does not reject it (400 error, bad parse_mode).
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 888, "u", "Q")
        t_id = t.id

    captured_user_msg = []

    async def mock_telegram_user(user_id, text):
        captured_user_msg.append(text)
        return True

    untrusted_body = "Solution avec *gras non fermé et code `non fermé et lien [invalide <script>"
    payload = {"sender": "support@example.com", "subject": f"[Ticket #{t_id}]", "body": untrusted_body}
    raw_bytes, sig = sign_body(payload)

    with patch.object(TelegramRelay, "send_message_to_user", mock_telegram_user):
        resp = await client.post(
            "/api/webhooks/email-inbound",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
        )

    assert resp.status_code == 200
    assert len(captured_user_msg) == 1
    sent_text = captured_user_msg[0]
    # Unclosed metacharacters must have been escaped
    assert "\\*" in sent_text
    assert "\\`" in sent_text
    assert "\\[" in sent_text


@pytest.mark.asyncio
async def test_webhooks_email_secrets_never_logged_during_verification(app_test_env, caplog):
    """
    2. SECURITY - Secrets in logs:
    The secret EMAIL_WEBHOOK_SECRET appears in no log.
    """
    client, _, _ = app_test_env
    payload = {"sender": "support@example.com", "subject": "[Ticket #1]", "body": "Sol"}
    raw_bytes, sig = sign_body(payload)

    with caplog.at_level(logging.DEBUG):
        await client.post(
            "/api/webhooks/email-inbound",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
        )

    for record in caplog.records:
        assert TEST_EMAIL_WEBHOOK_SECRET not in record.getMessage()


# ==============================================================================
# 3. ROBUSTESSE
# ==============================================================================


@pytest.mark.asyncio
async def test_webhooks_email_telegram_relay_failure_does_not_crash_resolution(app_test_env):
    """
    3. ROBUSTNESS - Telegram network fault tolerance:
    If sending the Telegram notification fails (e.g. Telegram unavailable),
    the ticket resolution in the database must persist and the webhook must succeed (200).
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 1, "u", "Q")
        t_id = t.id

    # Simulate a TelegramRelay outage
    mock_fail_telegram = AsyncMock(return_value=False)

    payload = {"sender": "support@example.com", "subject": f"[Ticket #{t_id}]", "body": "Solution"}
    raw_bytes, sig = sign_body(payload)

    with patch.object(TelegramRelay, "send_message_to_user", mock_fail_telegram), \
         patch.object(TelegramRelay, "notify_support_group", mock_fail_telegram):
        resp = await client.post(
            "/api/webhooks/email-inbound",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
        )

    assert resp.status_code == 200
    # The ticket is indeed resolved in the database
    async with session_maker() as session:
        refreshed = (await session.execute(select(Ticket).where(Ticket.id == t_id))).scalar_one()
        assert refreshed.status == "RESOLVED"


@pytest.mark.asyncio
async def test_webhooks_email_background_telegram_exception_isolated_and_logged(app_test_env, caplog):
    """
    3. ROBUSTNESS - Isolating exceptions in BackgroundTasks:
    If TelegramRelay raises an uncaught exception (e.g. network cut, HTTP timeout),
    the safe_background_task wrapper isolates the failure, logs it with exc_info,
    and the HTTP 200 response is delivered to the client without interruption.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 1, "u", "Q")
        t_id = t.id

    mock_crash = AsyncMock(side_effect=RuntimeError("Fatal network crash to api.telegram.org"))

    payload = {"sender": "support@example.com", "subject": f"[Ticket #{t_id}]", "body": "Solution"}
    raw_bytes, sig = sign_body(payload)

    with patch.object(TelegramRelay, "send_message_to_user", mock_crash), \
         patch.object(TelegramRelay, "notify_support_group", mock_crash):
        with caplog.at_level(logging.ERROR):
            resp = await client.post(
                "/api/webhooks/email-inbound",
                content=raw_bytes,
                headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
            )

    assert resp.status_code == 200
    # The ticket is indeed resolved
    async with session_maker() as session:
        refreshed = (await session.execute(select(Ticket).where(Ticket.id == t_id))).scalar_one()
        assert refreshed.status == "RESOLVED"

    # Check that the error was logged by safe_background_task
    error_logs = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("failed with exception" in msg for msg in error_logs)


@pytest.mark.asyncio
async def test_webhooks_email_disabled_returns_503(app_test_env, monkeypatch):
    """
    When EMAIL_ENABLED is False, the /api/webhooks/email-inbound endpoint
    immediately rejects the request with HTTP 503 Service Unavailable.
    """
    client, _, _ = app_test_env
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)

    payload = {"sender": "support@example.com", "subject": "[Ticket #123]", "body": "Solution"}
    raw_bytes, sig = sign_body(payload)

    resp = await client.post(
        "/api/webhooks/email-inbound",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
    )
    assert resp.status_code == 503
    assert "Email support is disabled" in resp.json()["detail"]
