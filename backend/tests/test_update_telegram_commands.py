import pytest
from unittest.mock import AsyncMock, patch

from scripts import update_telegram_commands as utc


@pytest.mark.asyncio
async def test_update_telegram_commands_exits_when_no_token(monkeypatch):
    monkeypatch.setattr(utc.settings, "TELEGRAM_BOT_TOKEN", "")
    with pytest.raises(SystemExit) as exc_info:
        await utc.main()
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_update_telegram_commands_registers_commands_successfully(monkeypatch, capsys):
    monkeypatch.setattr(utc.settings, "TELEGRAM_BOT_TOKEN", "123456:FakeTokenForScriptTest")
    mock_configure = AsyncMock()
    monkeypatch.setattr(utc, "configure_command_suggestions", mock_configure)

    with patch("scripts.update_telegram_commands.Bot") as MockBot:
        mock_bot_instance = AsyncMock()
        MockBot.return_value = mock_bot_instance

        await utc.main()

        mock_configure.assert_called_once_with(mock_bot_instance)
        mock_bot_instance.session.close.assert_called_once()
        captured = capsys.readouterr()
        assert "Successfully registered all command scopes" in captured.out


@pytest.mark.asyncio
async def test_update_telegram_commands_handles_failure(monkeypatch, capsys):
    monkeypatch.setattr(utc.settings, "TELEGRAM_BOT_TOKEN", "123456:FakeTokenForScriptTest")
    mock_configure = AsyncMock(side_effect=Exception("Telegram API network timeout"))
    monkeypatch.setattr(utc, "configure_command_suggestions", mock_configure)

    with patch("scripts.update_telegram_commands.Bot") as MockBot:
        mock_bot_instance = AsyncMock()
        MockBot.return_value = mock_bot_instance

        with pytest.raises(SystemExit) as exc_info:
            await utc.main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Failed to register commands" in captured.out
        mock_bot_instance.session.close.assert_called_once()
