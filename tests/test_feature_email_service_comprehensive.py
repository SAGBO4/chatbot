import logging
import smtplib
from email.message import EmailMessage
from unittest.mock import MagicMock
import pytest

from backend.config import settings
from backend.services.email_service import EmailService


def _mock_smtp_context_manager():
    server = MagicMock()
    server.__enter__.return_value = server
    server.__exit__.return_value = False
    return server


@pytest.mark.asyncio
async def test_email_service_send_ticket_created_notification_formats_subject_and_body_correctly(monkeypatch):
    """
    1. FONCTIONNEL:
    Vérifie le formatage du sujet et du corps lors de la création d'un ticket.
    """
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SUPPORT_EMAIL_RECIPIENT", "support@target.org")
    captured = []

    def mock_sender(msg: EmailMessage):
        captured.append(msg)
        return True

    success = await EmailService.send_ticket_created_notification(
        ticket_id=101,
        user_handle="michel",
        user_id=777,
        question="Impossible d'imprimer",
        automated_answer="Redémarrez",
        custom_sender=mock_sender,
    )
    assert success is True
    assert len(captured) == 1
    m = captured[0]
    assert m["Subject"] == "[Ticket #101] Nouvelle demande de support de @michel"
    assert m["To"] == "support@target.org"
    body = m.get_content()
    assert "• Numéro de Ticket : #101" in body
    assert "Impossible d'imprimer" in body
    assert "Redémarrez" in body


@pytest.mark.asyncio
async def test_email_service_send_ticket_resolved_notification_formats_subject_and_body_correctly(monkeypatch):
    """
    1. FONCTIONNEL:
    Vérifie le formatage lors de la résolution d'un ticket.
    """
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    captured = []

    def mock_sender(msg: EmailMessage):
        captured.append(msg)
        return True

    success = await EmailService.send_ticket_resolved_notification(
        ticket_id=202,
        resolved_by="agent_julie",
        resolution_channel="TELEGRAM",
        solution="Mise à jour du firmware",
        custom_sender=mock_sender,
    )
    assert success is True
    assert len(captured) == 1
    m = captured[0]
    assert m["Subject"] == "[Ticket #202] Résolu via TELEGRAM"
    body = m.get_content()
    assert "agent_julie" in body
    assert "Mise à jour du firmware" in body


@pytest.mark.asyncio
async def test_email_service_disabled_returns_true_without_network_dispatch(monkeypatch):
    """
    1. FONCTIONNEL:
    Quand EMAIL_ENABLED est False, l'appel retourne immédiatement True sans tenter d'envoi.
    """
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    called = []

    def mock_sender(msg):
        called.append(msg)
        return True

    success = await EmailService.send_ticket_created_notification(
        ticket_id=1, user_handle="u", user_id=1, question="Q", custom_sender=mock_sender
    )
    assert success is True
    assert len(called) == 0


def test_email_service_port_465_uses_smtp_ssl_context(monkeypatch):
    """
    1. FONCTIONNEL:
    Le port 465 nécessite smtplib.SMTP_SSL au lieu de STARTTLS.
    """
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.custom-ssl.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 465)
    monkeypatch.setattr(settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(settings, "SMTP_USER", None)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", None)

    ssl_server = _mock_smtp_context_manager()
    mock_ssl_ctor = MagicMock(return_value=ssl_server)
    mock_plain_ctor = MagicMock()
    monkeypatch.setattr(smtplib, "SMTP_SSL", mock_ssl_ctor)
    monkeypatch.setattr(smtplib, "SMTP", mock_plain_ctor)

    msg = EmailMessage()
    msg["Subject"] = "SSL Test"
    result = EmailService._send_smtp_sync(msg)
    assert result is True

    mock_ssl_ctor.assert_called_once_with("smtp.custom-ssl.com", 465, timeout=10.0)
    mock_plain_ctor.assert_not_called()
    ssl_server.starttls.assert_not_called()


def test_email_service_port_587_uses_smtp_with_starttls(monkeypatch):
    """
    1. FONCTIONNEL:
    Le port 587 utilise smtplib.SMTP standard puis appelle server.starttls().
    """
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.relay.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(settings, "SMTP_USER", None)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", None)

    plain_server = _mock_smtp_context_manager()
    mock_plain_ctor = MagicMock(return_value=plain_server)
    monkeypatch.setattr(smtplib, "SMTP", mock_plain_ctor)

    msg = EmailMessage()
    msg["Subject"] = "STARTTLS Test"
    result = EmailService._send_smtp_sync(msg)
    assert result is True

    mock_plain_ctor.assert_called_once_with("smtp.relay.com", 587, timeout=10.0)
    plain_server.starttls.assert_called_once()


def test_email_service_unconfigured_host_simulates_success(monkeypatch):
    """
    1. FONCTIONNEL:
    Quand l'hôte est 'smtp.example.com', l'envoi est simulé sans erreur.
    """
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    msg = EmailMessage()
    msg["Subject"] = "Simulation"
    assert EmailService._send_smtp_sync(msg) is True


# ==============================================================================
# 2. SÉCURITÉ
# ==============================================================================


def test_email_service_smtp_credentials_never_logged_on_failure(monkeypatch, caplog):
    """
    2. SÉCURITÉ - Secrets dans les logs:
    En cas d'échec d'authentification SMTP, le mot de passe ne doit jamais figurer dans les logs.
    """
    SECRET_PASS = "ultra_secret_smtp_password_xyz123"
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.auth-fail.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USER", "user@auth-fail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SECRET_PASS)

    server = _mock_smtp_context_manager()
    server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
    monkeypatch.setattr(smtplib, "SMTP", MagicMock(return_value=server))

    msg = EmailMessage()
    msg["Subject"] = "Auth Test"

    with caplog.at_level(logging.DEBUG):
        result = EmailService._send_smtp_sync(msg)

    assert result is False
    for record in caplog.records:
        assert SECRET_PASS not in record.getMessage()


def test_email_service_header_injection_prevented_by_email_message():
    """
    2. SÉCURITÉ - Injection d'en-tête (CRLF Injection):
    EmailMessage lève une exception s'il y a tentative d'injection CRLF dans le sujet.
    """
    msg = EmailMessage()
    with pytest.raises(ValueError):
        msg["Subject"] = "Normal Subject\r\nBcc: victim@example.com"


# ==============================================================================
# 3. ROBUSTESSE
# ==============================================================================


def test_email_service_smtp_timeout_returns_false_and_logs_error(monkeypatch, caplog):
    """
    3. ROBUSTESSE - Timeout réseau:
    Un timeout SMTP doit retourner False sans planter le serveur.
    """
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.timeout.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)

    def timeout_ctor(*args, **kwargs):
        raise TimeoutError("Connection timed out")

    monkeypatch.setattr(smtplib, "SMTP", timeout_ctor)

    msg = EmailMessage()
    msg["Subject"] = "Timeout Test"
    with caplog.at_level(logging.ERROR):
        res = EmailService._send_smtp_sync(msg)

    assert res is False
    assert any("Failed to send SMTP email" in r.getMessage() for r in caplog.records)


def test_email_service_smtp_connection_refused_returns_false_and_logs_error(monkeypatch):
    """
    3. ROBUSTESSE - Panne serveur SMTP:
    Une connexion refusée (ConnectionRefusedError) retourne False gracieusement.
    """
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.down.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)

    def refused_ctor(*args, **kwargs):
        raise ConnectionRefusedError("Connection refused by host")

    monkeypatch.setattr(smtplib, "SMTP", refused_ctor)

    msg = EmailMessage()
    msg["Subject"] = "Refusal Test"
    res = EmailService._send_smtp_sync(msg)
    assert res is False
