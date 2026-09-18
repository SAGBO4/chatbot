import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import User, Chat, Message, CallbackQuery
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from bot.handlers import community_handlers
from bot.handlers.community_handlers import (
    handle_community_ask,
    handle_community_resolve_yes,
    handle_community_resolve_no,
    handle_purge,
)

COMMUNITY_GROUP_ID = -100555111


@pytest.fixture
def memory_storage():
    return MemoryStorage()


def make_fsm_context(storage: MemoryStorage, user_id: int, chat_id: int) -> FSMContext:
    key = StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


async def _fake_get_community_group_id(backend_client=None):
    return COMMUNITY_GROUP_ID


@pytest.fixture(autouse=True)
def configure_community_group(monkeypatch):
    monkeypatch.setattr("app.config.settings.COMMUNITY_RESOLUTION_TIMEOUT_SECONDS", 600)
    monkeypatch.setattr("bot.group_scope.get_community_group_id", _fake_get_community_group_id)
    community_handlers._recent_bot_messages.clear()
    yield
    community_handlers._recent_bot_messages.clear()


def make_group_message(chat_id, user_id, text, username="alice"):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=chat_id, type="supergroup")
    message.from_user = MagicMock(spec=User, id=user_id, username=username, first_name="Alice")
    message.text = text
    message.answer = AsyncMock()
    message.reply = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_ask_outside_community_group_is_ignored(memory_storage):
    message = make_group_message(chat_id=-999999, user_id=1, text="/ask mon problème")
    state = make_fsm_context(memory_storage, 1, -999999)
    mock_client = AsyncMock()
    command = CommandObject(prefix="/", command="ask", args="mon problème")

    await handle_community_ask(message, command, state, bot=AsyncMock(), backend_client=mock_client)

    mock_client.query.assert_not_called()
    message.answer.assert_not_called()


@pytest.mark.asyncio
async def test_ask_without_question_text_replies_usage(memory_storage):
    message = make_group_message(chat_id=COMMUNITY_GROUP_ID, user_id=1, text="/ask")
    state = make_fsm_context(memory_storage, 1, COMMUNITY_GROUP_ID)
    mock_client = AsyncMock()
    command = CommandObject(prefix="/", command="ask", args=None)

    await handle_community_ask(message, command, state, bot=AsyncMock(), backend_client=mock_client)

    mock_client.query.assert_not_called()
    message.reply.assert_called_once()


@pytest.mark.asyncio
async def test_ask_triggers_query_and_tags_asker(memory_storage):
    message = make_group_message(chat_id=COMMUNITY_GROUP_ID, user_id=42, text="/ask comment reset mdp")
    state = make_fsm_context(memory_storage, 42, COMMUNITY_GROUP_ID)
    mock_client = AsyncMock()
    mock_client.query.return_value = {"found": True, "answer": "Cliquez sur mot de passe oublié."}
    sent_message = MagicMock(message_id=777)
    message.answer.return_value = sent_message
    command = CommandObject(prefix="/", command="ask", args="comment reset mdp")

    await handle_community_ask(message, command, state, bot=AsyncMock(), backend_client=mock_client)

    mock_client.query.assert_called_once_with(query="comment reset mdp", user_id=42, user_handle="alice")
    message.answer.assert_called_once()
    reply_text = message.answer.call_args[0][0]
    assert "@alice" in reply_text
    assert "Cliquez sur mot de passe oublié" in reply_text

    state_data = await state.get_data()
    assert state_data["last_question"] == "comment reset mdp"
    assert state_data["last_answer_message_id"] == 777
    assert 777 in community_handlers._recent_bot_messages[COMMUNITY_GROUP_ID]


def make_callback(storage, chat_id, user_id, data, text="Réponse précédente"):
    cb_message = MagicMock(spec=Message)
    cb_message.chat = MagicMock(spec=Chat, id=chat_id, type="supergroup")
    cb_message.text = text
    cb_message.edit_text = AsyncMock()
    cb_message.edit_reply_markup = AsyncMock()

    callback = MagicMock(spec=CallbackQuery)
    callback.id = "cb1"
    callback.from_user = MagicMock(spec=User, id=user_id, username="alice", first_name="Alice")
    callback.data = data
    callback.message = cb_message
    callback.answer = AsyncMock()
    return callback


@pytest.mark.asyncio
async def test_resolve_yes_confirms_and_clears_state(memory_storage):
    state = make_fsm_context(memory_storage, 42, COMMUNITY_GROUP_ID)
    await state.update_data(
        last_question="q", last_answer="a", last_answer_timestamp=time.time(),
        last_answer_message_id=1, asking_user_handle="alice",
    )
    callback = make_callback(memory_storage, COMMUNITY_GROUP_ID, 42, "cresolve:yes")

    await handle_community_resolve_yes(callback, state)

    callback.message.edit_text.assert_called_once()
    assert "résolu" in callback.message.edit_text.call_args[0][0].lower()
    assert await state.get_data() == {}


@pytest.mark.asyncio
async def test_resolve_yes_rejects_expired_answer(memory_storage, monkeypatch):
    monkeypatch.setattr("app.config.settings.COMMUNITY_RESOLUTION_TIMEOUT_SECONDS", 1)
    state = make_fsm_context(memory_storage, 42, COMMUNITY_GROUP_ID)
    await state.update_data(
        last_question="q", last_answer="a", last_answer_timestamp=time.time() - 100,
        last_answer_message_id=1, asking_user_handle="alice",
    )
    callback = make_callback(memory_storage, COMMUNITY_GROUP_ID, 42, "cresolve:yes")

    await handle_community_resolve_yes(callback, state)

    callback.message.edit_text.assert_not_called()
    callback.answer.assert_called_once()
    assert callback.answer.call_args.kwargs.get("show_alert") is True
    assert await state.get_data() == {}


@pytest.mark.asyncio
async def test_resolve_no_creates_ticket_and_only_posts_neutral_ack_in_community(memory_storage, monkeypatch):
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100777)
    state = make_fsm_context(memory_storage, 42, COMMUNITY_GROUP_ID)
    await state.update_data(
        last_question="Erreur de sync", last_answer="Solution auto",
        last_answer_timestamp=time.time(), last_answer_message_id=1, asking_user_handle="alice",
    )
    callback = make_callback(memory_storage, COMMUNITY_GROUP_ID, 42, "cresolve:no")

    mock_client = AsyncMock()
    mock_client.create_ticket.return_value = {"id": 55, "user_id": 42}
    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = MagicMock(message_id=999)

    await handle_community_resolve_no(callback, state, bot=mock_bot, backend_client=mock_client)

    mock_client.create_ticket.assert_called_once_with(
        user_id=42, user_handle="alice", question="Erreur de sync", automated_answer="Solution auto"
    )
    # Ticket card only posted to the admin group, not the community group
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args.kwargs["chat_id"] == -100777

    # Community message updated with a neutral acknowledgement only
    ack_text = callback.message.edit_text.call_args[0][0]
    assert "Ticket ouvert" in ack_text
    assert "Erreur de sync" not in ack_text
    assert "Solution auto" not in ack_text


@pytest.mark.asyncio
async def test_purge_rejects_non_admin(memory_storage, monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return False
    monkeypatch.setattr(community_handlers, "is_group_admin", fake_is_admin)

    message = make_group_message(chat_id=COMMUNITY_GROUP_ID, user_id=1, text="/purge 5")
    community_handlers._recent_bot_messages[COMMUNITY_GROUP_ID].append(123)
    mock_bot = AsyncMock()

    await handle_purge(message, bot=mock_bot)

    mock_bot.delete_message.assert_not_called()
    message.reply.assert_called_once()
    assert "administrateurs" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_expire_resolution_buttons_disables_keyboard_when_still_pending(memory_storage):
    state = make_fsm_context(memory_storage, 42, COMMUNITY_GROUP_ID)
    timestamp = time.time()
    await state.update_data(last_question="q", last_answer="a", last_answer_timestamp=timestamp)
    mock_bot = AsyncMock()

    await community_handlers._expire_resolution_buttons(mock_bot, state, COMMUNITY_GROUP_ID, 777, timestamp)

    mock_bot.edit_message_reply_markup.assert_called_once_with(
        chat_id=COMMUNITY_GROUP_ID, message_id=777, reply_markup=None
    )
    assert await state.get_data() == {}


@pytest.mark.asyncio
async def test_expire_resolution_buttons_noop_when_already_resolved(memory_storage):
    state = make_fsm_context(memory_storage, 42, COMMUNITY_GROUP_ID)
    # Already resolved: state was cleared, so the stored timestamp no longer matches
    mock_bot = AsyncMock()

    await community_handlers._expire_resolution_buttons(mock_bot, state, COMMUNITY_GROUP_ID, 777, time.time())

    mock_bot.edit_message_reply_markup.assert_not_called()


@pytest.mark.asyncio
async def test_purge_deletes_recent_bot_messages_for_admin(memory_storage, monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return True
    monkeypatch.setattr(community_handlers, "is_group_admin", fake_is_admin)

    message = make_group_message(chat_id=COMMUNITY_GROUP_ID, user_id=1, text="/purge 2")
    community_handlers._recent_bot_messages[COMMUNITY_GROUP_ID].extend([1, 2, 3])
    mock_bot = AsyncMock()

    await handle_purge(message, bot=mock_bot)

    assert mock_bot.delete_message.call_count == 2
    message.reply.assert_called_once()
    assert "2 message" in message.reply.call_args[0][0]
