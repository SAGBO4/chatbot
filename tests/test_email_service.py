import pytest
from backend.config import settings
from backend.services.email_service import EmailService


@pytest.mark.asyncio
async def test_email_service_disabled():
    settings.EMAIL_ENABLED = False
    result = await EmailService.send_ticket_created_notification(
        ticket_id=42,
        user_handle="alice",
        user_id=12345,
        question="Help with login",
    )
    assert result is True


@pytest.mark.asyncio
async def test_email_service_ticket_created_and_resolved():
    settings.EMAIL_ENABLED = True
    settings.SUPPORT_EMAIL_RECIPIENT = "support@test.org"
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

    settings.EMAIL_ENABLED = False
