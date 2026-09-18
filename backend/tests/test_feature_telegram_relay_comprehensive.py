import logging
import pytest
import httpx
from unittest.mock import AsyncMock

from backend.config import settings
from backend.services.telegram_relay import TelegramRelay


@pytest.mark.asyncio
async def test_telegram_relay_send_message_to_user_happy_path_succeeds(monkeypatch):
    """
    1. FONCTIONNEL - Happy Path:
    Vérifie l'envoi d'un message direct à un utilisateur via l'API Telegram sendMessage.
    """
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    mock_resp = httpx.Response(status_code=200, json={"ok": True})
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.is_closed = False

    TelegramRelay.set_shared_client(mock_client)
    try:
        success = await TelegramRelay.send_message_to_user(12345, "Bonjour utilisateur")
        assert success is True
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["chat_id"] == 12345
        assert call_kwargs["json"]["text"] == "Bonjour utilisateur"
        assert call_kwargs["json"]["parse_mode"] == "Markdown"
    finally:
        TelegramRelay.set_shared_client(None)


@pytest.mark.asyncio
async def test_telegram_relay_notify_support_group_happy_path_succeeds(monkeypatch):
    """
    1. FONCTIONNEL - Notification groupe support:
    Vérifie la transmission d'un message d'alerte au groupe support Telegram configuré.
    """
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", -100987654321)

    mock_resp = httpx.Response(status_code=200, json={"ok": True})
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.is_closed = False

    TelegramRelay.set_shared_client(mock_client)
    try:
        success = await TelegramRelay.notify_support_group("Nouveau ticket #5")
        assert success is True
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["chat_id"] == -100987654321
        assert "Nouveau ticket #5" in call_kwargs["json"]["text"]
    finally:
        TelegramRelay.set_shared_client(None)


@pytest.mark.asyncio
async def test_telegram_relay_unconfigured_token_simulates_success(monkeypatch):
    """
    1. FONCTIONNEL:
    Quand le token est 'placeholder_token' ou vide, le message est simulé avec succès.
    """
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "placeholder_token")
    success = await TelegramRelay.send_message_to_user(1, "Test")
    assert success is True


@pytest.mark.asyncio
async def test_telegram_relay_unconfigured_support_group_simulates_success(monkeypatch):
    """
    1. FONCTIONNEL:
    Quand le groupe support est 0 (non configuré), le relay simule sans crash.
    """
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "real_token")
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", 0)
    success = await TelegramRelay.notify_support_group("Test")
    assert success is True


@pytest.mark.asyncio
async def test_telegram_relay_markdown_failure_falls_back_to_plain_text(monkeypatch, caplog):
    """
    1. FONCTIONNEL & ROBUSTESSE:
    Si l'envoi en parse_mode Markdown échoue (ex: erreur 400 Bad Request syntaxe markdown),
    le relais retente immédiatement en texte brut (sans parse_mode).
    """
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")

    # 1er appel: 400 Markdown Error, 2e appel: 200 OK en plain text
    resp_bad = httpx.Response(status_code=400, text="Can't parse entities")
    resp_ok = httpx.Response(status_code=200, json={"ok": True})

    mock_client = AsyncMock()
    mock_client.post.side_effect = [resp_bad, resp_ok]
    mock_client.is_closed = False

    TelegramRelay.set_shared_client(mock_client)
    try:
        with caplog.at_level(logging.WARNING):
            success = await TelegramRelay.send_message_to_user(1, "Texte avec *markdown problématique")

        assert success is True
        assert mock_client.post.call_count == 2
        # Le 2e appel ne doit pas avoir parse_mode
        second_call_json = mock_client.post.call_args_list[1][1]["json"]
        assert "parse_mode" not in second_call_json
        assert any("retrying in plain text" in r.getMessage() for r in caplog.records)
    finally:
        TelegramRelay.set_shared_client(None)


@pytest.mark.asyncio
async def test_telegram_relay_message_length_truncated_to_4000_chars(monkeypatch):
    """
    1. FONCTIONNEL:
    Un texte de plus de 4000 caractères doit être tronqué pour respecter la limite Telegram.
    """
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    mock_client = AsyncMock()
    mock_client.post.return_value = httpx.Response(status_code=200, json={"ok": True})
    mock_client.is_closed = False

    TelegramRelay.set_shared_client(mock_client)
    try:
        long_msg = "Z" * 5000
        await TelegramRelay.send_message_to_user(1, long_msg)
        sent_text = mock_client.post.call_args[1]["json"]["text"]
        assert len(sent_text) <= 4000
        assert sent_text.endswith("...(tronqué)")
    finally:
        TelegramRelay.set_shared_client(None)


# ==============================================================================
# 3. ROBUSTESSE
# ==============================================================================


@pytest.mark.asyncio
async def test_telegram_relay_http_timeout_returns_false(monkeypatch, caplog):
    """
    3. ROBUSTESSE - Timeout réseau:
    Un timeout HTTP vers l'API Telegram retourne False sans planter le caller.
    """
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("Telegram API timeout")
    mock_client.is_closed = False

    TelegramRelay.set_shared_client(mock_client)
    try:
        with caplog.at_level(logging.ERROR):
            success = await TelegramRelay.send_message_to_user(1, "Test")
        assert success is False
        assert any("Failed to relay message" in r.getMessage() for r in caplog.records)
    finally:
        TelegramRelay.set_shared_client(None)


@pytest.mark.asyncio
async def test_telegram_relay_network_connection_error_returns_false(monkeypatch, caplog):
    """
    3. ROBUSTESSE - Erreur de connexion:
    Une erreur de connexion (ConnectError) retourne False gracieusement.
    """
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", -100123456789)

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ConnectError("Network unreachable")
    mock_client.is_closed = False

    TelegramRelay.set_shared_client(mock_client)
    try:
        success = await TelegramRelay.notify_support_group("Test group")
        assert success is False
    finally:
        TelegramRelay.set_shared_client(None)
