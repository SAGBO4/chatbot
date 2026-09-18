import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import User, Chat, Message
from aiogram.filters import CommandObject

from bot import access_control
from bot.handlers.setup_handlers import handle_whitelist


def make_message(user_id, username="owner_x"):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=1, type="private")
    message.from_user = MagicMock(spec=User, id=user_id, username=username, first_name="Owner")
    message.reply = AsyncMock()
    return message


@pytest.fixture(autouse=True)
def configure_owner(monkeypatch):
    monkeypatch.setattr("backend.config.settings.BOT_OWNER_TELEGRAM_ID", 999)
    access_control.invalidate_whitelist_cache()
    yield
    access_control.invalidate_whitelist_cache()


@pytest.mark.asyncio
async def test_owner_can_add_to_whitelist():
    message = make_message(user_id=999)
    mock_client = AsyncMock()
    command = CommandObject(prefix="/", command="whitelist", args="add 42")

    await handle_whitelist(message, command, backend_client=mock_client)

    mock_client.whitelist_add.assert_called_once_with(42, added_by="owner_x")
    assert "ajouté" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_owner_can_remove_from_whitelist():
    message = make_message(user_id=999)
    mock_client = AsyncMock()
    mock_client.whitelist_remove.return_value = True
    command = CommandObject(prefix="/", command="whitelist", args="remove 42")

    await handle_whitelist(message, command, backend_client=mock_client)

    mock_client.whitelist_remove.assert_called_once_with(42)
    assert "retiré" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_non_owner_cannot_manage_whitelist():
    message = make_message(user_id=1)
    mock_client = AsyncMock()
    command = CommandObject(prefix="/", command="whitelist", args="add 42")

    await handle_whitelist(message, command, backend_client=mock_client)

    mock_client.whitelist_add.assert_not_called()
    assert "propriétaire" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_whitelisted_non_owner_admin_cannot_manage_whitelist(monkeypatch):
    # A whitelisted admin is authorized for other actions, but /whitelist
    # itself remains owner-only.
    message = make_message(user_id=42)
    mock_client = AsyncMock()
    command = CommandObject(prefix="/", command="whitelist", args="add 100")

    await handle_whitelist(message, command, backend_client=mock_client)

    mock_client.whitelist_add.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_args_shows_usage():
    message = make_message(user_id=999)
    mock_client = AsyncMock()
    command = CommandObject(prefix="/", command="whitelist", args="bogus")

    await handle_whitelist(message, command, backend_client=mock_client)

    mock_client.whitelist_add.assert_not_called()
    mock_client.whitelist_remove.assert_not_called()
    assert "Utilisation" in message.reply.call_args[0][0]
