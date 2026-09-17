import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import User, Chat, Message
from aiogram.filters import CommandObject

from bot import access_control, language
from bot.handlers.setup_handlers import handle_language


def make_message(user_id, username="admin_x"):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=1, type="private")
    message.from_user = MagicMock(spec=User, id=user_id, username=username, first_name="Admin")
    message.reply = AsyncMock()
    return message


@pytest.fixture(autouse=True)
def reset_caches(monkeypatch):
    monkeypatch.setattr("backend.config.settings.BOT_OWNER_TELEGRAM_ID", 999)
    access_control.invalidate_whitelist_cache()
    language.invalidate_language_cache()
    yield
    access_control.invalidate_whitelist_cache()
    language.invalidate_language_cache()


@pytest.mark.asyncio
async def test_owner_can_change_language_to_english():
    message = make_message(user_id=999)
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "fr"
    command = CommandObject(prefix="/", command="language", args="en")

    await handle_language(message, command, backend_client=mock_client)

    mock_client.set_setting.assert_called_once_with("language", "en", updated_by="admin_x")
    assert "English" in message.reply.call_args[0][0] or "en" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_change_language():
    message = make_message(user_id=1)
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "fr"
    mock_client.is_whitelisted.return_value = False
    command = CommandObject(prefix="/", command="language", args="en")

    await handle_language(message, command, backend_client=mock_client)

    mock_client.set_setting.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_language_argument_rejected():
    message = make_message(user_id=999)
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "fr"
    command = CommandObject(prefix="/", command="language", args="de")

    await handle_language(message, command, backend_client=mock_client)

    mock_client.set_setting.assert_not_called()
    assert "Utilisation" in message.reply.call_args[0][0] or "Usage" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_response_after_switching_to_english_is_in_english():
    message = make_message(user_id=999)
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "fr"
    command = CommandObject(prefix="/", command="language", args="en")

    await handle_language(message, command, backend_client=mock_client)

    reply_text = message.reply.call_args[0][0]
    assert "Bot language set to" in reply_text
