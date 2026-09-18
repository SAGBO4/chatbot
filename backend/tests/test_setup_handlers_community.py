import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import User, Chat, Message

from bot import access_control, group_scope
from bot.handlers.setup_handlers import handle_setup_community


def make_group_message(user_id, chat_id=-100555, chat_type="supergroup", username="admin_x"):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=chat_id, type=chat_type)
    message.from_user = MagicMock(spec=User, id=user_id, username=username, first_name="Admin")
    message.reply = AsyncMock()
    return message


@pytest.fixture(autouse=True)
def configure_owner(monkeypatch):
    monkeypatch.setattr("backend.config.settings.BOT_OWNER_TELEGRAM_ID", 999)
    access_control.invalidate_whitelist_cache()
    group_scope.invalidate_community_group_cache()
    yield
    access_control.invalidate_whitelist_cache()
    group_scope.invalidate_community_group_cache()


@pytest.mark.asyncio
async def test_owner_can_configure_community_group():
    message = make_group_message(user_id=999, chat_id=-100555)
    mock_client = AsyncMock()

    await handle_setup_community(message, backend_client=mock_client)

    mock_client.set_setting.assert_called_once_with("community_group_id", "-100555", updated_by="admin_x")
    assert "groupe communautaire actif" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_whitelisted_admin_can_configure_community_group(monkeypatch):
    mock_client = AsyncMock()
    mock_client.is_whitelisted.return_value = True
    message = make_group_message(user_id=42, chat_id=-100555)

    await handle_setup_community(message, backend_client=mock_client)

    mock_client.set_setting.assert_called_once()


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_configure_community_group():
    mock_client = AsyncMock()
    mock_client.is_whitelisted.return_value = False
    message = make_group_message(user_id=1, chat_id=-100555)

    await handle_setup_community(message, backend_client=mock_client)

    mock_client.set_setting.assert_not_called()
    assert "autorisé" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_configuring_in_private_chat_shows_instructions():
    message = make_group_message(user_id=999, chat_id=999, chat_type="private")
    mock_client = AsyncMock()

    await handle_setup_community(message, backend_client=mock_client)

    mock_client.set_setting.assert_not_called()
    assert "groupe" in message.reply.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_reconfiguring_replaces_previous_group():
    mock_client = AsyncMock()
    first_message = make_group_message(user_id=999, chat_id=-100111)
    await handle_setup_community(first_message, backend_client=mock_client)

    second_message = make_group_message(user_id=999, chat_id=-100222)
    await handle_setup_community(second_message, backend_client=mock_client)

    assert mock_client.set_setting.call_count == 2
    last_call_args = mock_client.set_setting.call_args_list[-1]
    assert last_call_args.args[1] == "-100222"


@pytest.mark.asyncio
async def test_cache_invalidated_after_successful_configuration(monkeypatch):
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = None
    # Prime the cache with "unconfigured"
    await group_scope.get_community_group_id(backend_client=mock_client)

    message = make_group_message(user_id=999, chat_id=-100555)
    mock_client.get_setting.return_value = "-100555"
    await handle_setup_community(message, backend_client=mock_client)

    # Cache should be invalidated, so the next resolution sees the new value
    # instead of the primed "unconfigured" cache.
    assert await group_scope.is_community_group_chat(-100555, backend_client=mock_client) is True
