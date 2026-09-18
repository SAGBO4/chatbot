import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import User, Chat, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from bot import access_control, group_scope, language
from bot.handlers.setup_handlers import _should_show_setup_tutorial, handle_start_setup_tutorial


def make_private_message(user_id, username="admin_x"):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=user_id, type="private")
    message.from_user = MagicMock(spec=User, id=user_id, username=username, first_name="Admin")
    message.answer = AsyncMock()
    return message


def make_fsm_context(user_id):
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=user_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


@pytest.fixture(autouse=True)
def reset_caches(monkeypatch):
    monkeypatch.setattr("backend.config.settings.BOT_OWNER_TELEGRAM_ID", 999)
    access_control.invalidate_whitelist_cache()
    group_scope.invalidate_community_group_cache()
    language.invalidate_language_cache()
    yield
    access_control.invalidate_whitelist_cache()
    group_scope.invalidate_community_group_cache()
    language.invalidate_language_cache()


async def _patch_no_community_group(monkeypatch):
    async def fake(backend_client=None):
        return None
    monkeypatch.setattr("bot.handlers.setup_handlers.get_community_group_id", fake)


async def _patch_community_group_configured(monkeypatch):
    async def fake(backend_client=None):
        return -100555
    monkeypatch.setattr("bot.handlers.setup_handlers.get_community_group_id", fake)


@pytest.mark.asyncio
async def test_owner_sees_tutorial_when_no_community_group(monkeypatch):
    await _patch_no_community_group(monkeypatch)
    message = make_private_message(user_id=999)

    should_show = await _should_show_setup_tutorial(message)

    assert should_show is True


@pytest.mark.asyncio
async def test_owner_does_not_see_tutorial_when_community_group_configured(monkeypatch):
    await _patch_community_group_configured(monkeypatch)
    message = make_private_message(user_id=999)

    should_show = await _should_show_setup_tutorial(message)

    assert should_show is False


@pytest.mark.asyncio
async def test_non_authorized_user_does_not_see_tutorial(monkeypatch):
    await _patch_no_community_group(monkeypatch)
    message = make_private_message(user_id=1)

    should_show = await _should_show_setup_tutorial(message)

    assert should_show is False


@pytest.mark.asyncio
async def test_group_chat_never_shows_tutorial(monkeypatch):
    await _patch_no_community_group(monkeypatch)
    message = make_private_message(user_id=999)
    message.chat = MagicMock(spec=Chat, id=-100, type="supergroup")

    should_show = await _should_show_setup_tutorial(message)

    assert should_show is False


@pytest.mark.asyncio
async def test_handler_sends_tutorial_text():
    message = make_private_message(user_id=999)
    state = make_fsm_context(999)
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "fr"

    await handle_start_setup_tutorial(message, state, backend_client=mock_client)

    message.answer.assert_called_once()
    assert "communautaire" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_handler_sends_tutorial_text_in_english():
    message = make_private_message(user_id=999)
    state = make_fsm_context(999)
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"

    await handle_start_setup_tutorial(message, state, backend_client=mock_client)

    message.answer.assert_called_once()
    assert "Welcome" in message.answer.call_args[0][0]
