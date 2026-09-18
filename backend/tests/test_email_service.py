import smtplib
from email.message import EmailMessage
from unittest.mock import MagicMock

import pytest
from app.config import settings
from app.services.email_service import EmailService


@pytest.mark.asyncio
async def test_email_service_disabled(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    result = await EmailService.send_ticket_created_notification(
        ticket_id=42,
        user_handle="alice",
        user_id=12345,
        question="Help with login",
    )
    assert result is True


@pytest.mark.asyncio
async def test_email_service_ticket_created_and_resolved(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SUPPORT_EMAIL_RECIPIENT", "support@test.org")
    captured_messages = []

    def mock_sender(msg):
        captured_messages.append(msg)
        return True

    # 1. Send created
    created_ok = await EmailService.send_ticket_created_notification(
        ticket_id=55,
        user_handle="bob_user",
        user_id=987,
        question="Panne de réseau",
        automated_answer="Vérifiez le wifi",
        custom_sender=mock_sender,
    )
    assert created_ok is True
    assert len(captured_messages) == 1
    m1 = captured_messages[0]
    assert m1["Subject"] == "[Ticket #55] Nouvelle demande de support de @bob_user"
    assert m1["To"] == "support@test.org"
    assert "Panne de réseau" in m1.get_content()

    # 2. Send resolved
    resolved_ok = await EmailService.send_ticket_resolved_notification(
        ticket_id=55,
        resolved_by="agent_claire",
        resolution_channel="TELEGRAM",
        solution="Redémarrez le routeur",
        custom_sender=mock_sender,
    )
    assert resolved_ok is True
    assert len(captured_messages) == 2
    m2 = captured_messages[1]
    assert m2["Subject"] == "[Ticket #55] Résolu via TELEGRAM"
    assert "agent_claire" in m2.get_content()


def _mock_smtp_context_manager():
    """A MagicMock that behaves like the object returned by smtplib.SMTP(...)/SMTP_SSL(...)."""
    server = MagicMock()
    server.__enter__.return_value = server
    server.__exit__.return_value = False
    return server


def test_send_smtp_sync_uses_ssl_for_implicit_tls_port_465(monkeypatch):
    """Port 465 (Gmail SSL, iCloud, ...) requires SMTP_SSL, not STARTTLS."""
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 465)
    monkeypatch.setattr(settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(settings, "SMTP_USER", None)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", None)

    ssl_server = _mock_smtp_context_manager()
    starttls_ctor = MagicMock()
    monkeypatch.setattr(smtplib, "SMTP_SSL", MagicMock(return_value=ssl_server))
    monkeypatch.setattr(smtplib, "SMTP", starttls_ctor)

    msg = EmailMessage()
    msg["Subject"] = "test"
    assert EmailService._send_smtp_sync(msg) is True

    smtplib.SMTP_SSL.assert_called_once_with("smtp.gmail.com", 465, timeout=10.0)
    starttls_ctor.assert_not_called()
    ssl_server.starttls.assert_not_called()


def test_send_smtp_sync_uses_starttls_for_port_587(monkeypatch):
    """Port 587 keeps using plain SMTP + starttls(), as before."""
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(settings, "SMTP_USER", None)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", None)

    plain_server = _mock_smtp_context_manager()
    ssl_ctor = MagicMock()
    monkeypatch.setattr(smtplib, "SMTP", MagicMock(return_value=plain_server))
    monkeypatch.setattr(smtplib, "SMTP_SSL", ssl_ctor)

    msg = EmailMessage()
    msg["Subject"] = "test"
    assert EmailService._send_smtp_sync(msg) is True

    smtplib.SMTP.assert_called_once_with("smtp-relay.brevo.com", 587, timeout=10.0)
    ssl_ctor.assert_not_called()
    plain_server.starttls.assert_called_once()
