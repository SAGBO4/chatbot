"""
Representative per-handler-module English-language coverage (task 4.3): for
each handler module, confirm at least one bot-authored message renders in
English when the active language is "en", proving the module is wired
through app.i18n.t() rather than hardcoded French.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import User, Chat, Message, CallbackQuery
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from app.config import settings
from bot.handlers.user_handlers import handle_start, handle_user_query, handle_webapp
from bot.keyboards import get_community_resolution_keyboard, get_resolution_keyboard, get_webapp_keyboard
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


def _labels(markup):
    return [(button.text, button.callback_data) for row in markup.inline_keyboard for button in row]


@pytest.mark.parametrize(
    "lang,yes,no",
    [("fr", "✅ OUI", "❌ NON"), ("en", "✅ YES", "❌ NO")],
)
def test_resolution_keyboards_follow_the_language_and_keep_their_callback_data(lang, yes, no):
    assert _labels(get_resolution_keyboard(7, lang=lang)) == [(yes, "resolve:yes:7"), (no, "resolve:no:7")]
    assert _labels(get_community_resolution_keyboard(lang)) == [(yes, "cresolve:yes"), (no, "cresolve:no")]


def test_resolution_keyboards_default_to_french():
    assert _labels(get_resolution_keyboard())[0][0] == "✅ OUI"


@pytest.mark.parametrize("lang,label", [("fr", "Centre d'Assistance Stack"), ("en", "Stack Support Center")])
def test_webapp_keyboard_label_follows_the_language(lang, label):
    markup = get_webapp_keyboard("https://example.test/app", lang=lang)
    assert label in markup.inline_keyboard[0][0].text


@pytest.mark.asyncio
async def test_private_answer_buttons_are_in_english_when_the_bot_is_in_english():
    message = MagicMock(spec=Message)
    message.text = "How do I export my wallet?"
    message.from_user = MagicMock(spec=User, id=5, username="alice", first_name="Alice")
    message.answer = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"
    mock_client.query.return_value = {"answer": "Open Settings, then Export."}

    await handle_user_query(message, make_fsm_context(5, 5), backend_client=mock_client)

    markup = message.answer.call_args.kwargs["reply_markup"]
    assert [text for text, _ in _labels(markup)] == ["✅ YES", "❌ NO"]


@pytest.mark.asyncio
async def test_webapp_command_is_in_english_when_the_bot_is_in_english(monkeypatch):
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()

    monkeypatch.setattr(settings, "TELEGRAM_WEBAPP_URL", None)
    await handle_webapp(message, backend_client=mock_client)
    assert "not configured" in message.answer.call_args[0][0]

    monkeypatch.setattr(settings, "TELEGRAM_WEBAPP_URL", "https://example.test/app")
    await handle_webapp(message, backend_client=mock_client)
    assert "support center" in message.answer.call_args[0][0]
    assert "Open the Support App" in message.answer.call_args.kwargs["reply_markup"].inline_keyboard[0][0].text
