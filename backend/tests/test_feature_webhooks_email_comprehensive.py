import asyncio
import hashlib
import hmac
import json
import logging
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Ticket, TicketStatus, KnowledgeArticle
from app.services.ticket_service import TicketService
from app.services.telegram_relay import TelegramRelay
from tests.conftest import TEST_EMAIL_WEBHOOK_SECRET


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

