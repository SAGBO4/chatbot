"""
Representative per-handler-module English-language coverage (task 4.3): for
each handler module, confirm at least one bot-authored message renders in
English when the active language is "en", proving the module is wired
through bot.i18n.t() rather than hardcoded French.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import User, Chat, Message, CallbackQuery
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from bot.handlers.user_handlers import handle_start
from bot.handlers.crypto_handlers import _handle_asset_command
from bot.handlers import community_handlers, moderation_handlers


def make_fsm_context(user_id=1, chat_id=1):
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


@pytest.mark.asyncio
async def test_user_handlers_welcome_in_english():
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    state = make_fsm_context()
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"

    await handle_start(message, state, backend_client=mock_client)

    assert "welcome" in message.answer.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_crypto_handlers_unrecognized_asset_in_english():
    message = MagicMock(spec=Message)
    message.reply = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"
    import httpx
    response = MagicMock(status_code=404)
    mock_client.get_crypto_price.side_effect = httpx.HTTPStatusError("404", request=MagicMock(), response=response)

    await _handle_asset_command(message, "notacoin", backend_client=mock_client)

    assert "not recognized" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_community_handlers_ask_usage_in_english(monkeypatch):
    async def fake_is_community(chat_id, backend_client=None):
        return True
    monkeypatch.setattr(community_handlers, "_is_community_group_chat", fake_is_community)

    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=-100, type="supergroup")
    message.from_user = MagicMock(spec=User, id=1, username="alice", first_name="Alice")
    message.reply = AsyncMock()
    state = make_fsm_context()
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"
    command = CommandObject(prefix="/", command="ask", args=None)

    await community_handlers.handle_community_ask(message, command, state, bot=AsyncMock(), backend_client=mock_client)

    assert "Usage" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_moderation_handlers_mute_success_in_english(monkeypatch):
    async def fake_is_community(chat_id, backend_client=None):
        return True
    monkeypatch.setattr(moderation_handlers, "is_community_group_chat", fake_is_community)

    async def fake_is_admin(bot, chat_id, user_id):
        return True
    monkeypatch.setattr(moderation_handlers, "is_group_admin", fake_is_admin)

    reply_target = MagicMock(spec=Message)
    reply_target.from_user = MagicMock(spec=User, id=55, username="bob", first_name="Bob")

    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=-100, type="supergroup")
    message.from_user = MagicMock(spec=User, id=1, username="admin_x", first_name="Admin")
    message.reply_to_message = reply_target
    message.reply = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"
    bot = AsyncMock()
    command = CommandObject(prefix="/", command="mute", args=None)

    await moderation_handlers.handle_mute(message, command, bot, backend_client=mock_client)

    assert "muted" in message.reply.call_args[0][0]
