"""
A user or community member can ask a question by sending a screenshot instead of (or with) text.

The image is never run through OCR or a vision model - it is only ever shown to a human: an agent in
the support group, once the question is escalated to a ticket. A caption (if any) is what the
knowledge base is searched with; with no caption, a placeholder question is used instead, so the flow
is identical to an unmatched text question (the "not found, escalate?" prompt).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import User, Chat, Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from bot.handlers.user_handlers import handle_user_photo_query, handle_resolve_no
from bot.handlers import community_handlers
from bot.handlers.community_handlers import (
    handle_community_photo_question,
    handle_community_resolve_no,
)
from bot.ticket_escalation import create_ticket_and_notify_admin_group
from bot.api_client import BackendClient

COMMUNITY_GROUP_ID = -100555111


@pytest.fixture
def memory_storage():
    return MemoryStorage()


def make_fsm_context(storage: MemoryStorage, user_id: int, chat_id: int) -> FSMContext:
    key = StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


def make_photo_sizes(file_id: str = "full_res_file_id"):
    """A realistic `message.photo`: Telegram sends thumbnail-to-largest; handlers must use the last one."""
    return [
        MagicMock(spec=PhotoSize, file_id="thumbnail_file_id"),
        MagicMock(spec=PhotoSize, file_id=file_id),
    ]


def make_private_photo_message(user_id: int, caption=None, file_id="full_res_file_id"):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=user_id, type="private")
    message.from_user = MagicMock(spec=User, id=user_id, username=f"user{user_id}", first_name="User")
    message.text = None
    message.caption = caption
    message.photo = make_photo_sizes(file_id)
    message.answer = AsyncMock()
    return message


def make_group_photo_message(chat_id, user_id, caption=None, file_id="full_res_file_id", username="alice"):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=chat_id, type="supergroup")
    message.from_user = MagicMock(spec=User, id=user_id, username=username, first_name="Alice")
    message.text = None
    message.caption = caption
    message.photo = make_photo_sizes(file_id)
    message.answer = AsyncMock()
    message.reply = AsyncMock()
    return message


# ---------------------------------------------------------------------------
# Private chat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_private_photo_with_caption_is_searched_with_the_caption(memory_storage):
    message = make_private_photo_message(1, caption="Comment restaurer mon wallet ?")
    state = make_fsm_context(memory_storage, 1, 1)
    client = AsyncMock()
    client.query.return_value = {"found": True, "answer": "Utilisez votre phrase de récupération."}

    await handle_user_photo_query(message, state, backend_client=client)

    client.query.assert_called_once()
    assert client.query.call_args.kwargs["query"] == "Comment restaurer mon wallet ?"
    message.answer.assert_called_once()
    assert "phrase de récupération" in message.answer.call_args[0][0]

    data = await state.get_data()
    assert data["last_photo_file_id"] == "full_res_file_id"
    assert data["last_question"] == "Comment restaurer mon wallet ?"


@pytest.mark.asyncio
async def test_private_photo_without_caption_uses_a_placeholder_question(memory_storage):
    message = make_private_photo_message(2, caption=None)
    state = make_fsm_context(memory_storage, 2, 2)
    client = AsyncMock()
    client.query.return_value = {"found": False, "answer": "Je n'ai pas trouvé de réponse..."}

    await handle_user_photo_query(message, state, backend_client=client)

    client.query.assert_called_once()
    question_sent = client.query.call_args.kwargs["query"]
    assert question_sent  # never empty: the backend would 422 on an empty query
    data = await state.get_data()
    assert data["last_question"] == question_sent
    assert data["last_photo_file_id"] == "full_res_file_id"


@pytest.mark.asyncio
async def test_private_photo_empty_caption_is_treated_like_no_caption(memory_storage):
    """A caption of only whitespace must not be sent to the backend as-is (it would 422)."""
    message = make_private_photo_message(3, caption="   ")
    state = make_fsm_context(memory_storage, 3, 3)
    client = AsyncMock()
    client.query.return_value = {"found": False, "answer": "..."}

    await handle_user_photo_query(message, state, backend_client=client)

    assert client.query.call_args.kwargs["query"].strip()


@pytest.mark.asyncio
async def test_private_photo_uses_the_largest_size_not_the_thumbnail(memory_storage):
    message = make_private_photo_message(4, caption="q", file_id="largest")
    state = make_fsm_context(memory_storage, 4, 4)
    client = AsyncMock()
    client.query.return_value = {"found": True, "answer": "a"}

    await handle_user_photo_query(message, state, backend_client=client)

    data = await state.get_data()
    assert data["last_photo_file_id"] == "largest"
    assert data["last_photo_file_id"] != "thumbnail_file_id"


@pytest.mark.asyncio
async def test_private_photo_caption_too_long_is_rejected_without_a_backend_call(memory_storage):
    message = make_private_photo_message(5, caption="x" * 4001)
    state = make_fsm_context(memory_storage, 5, 5)
    client = AsyncMock()

    await handle_user_photo_query(message, state, backend_client=client)

    client.query.assert_not_called()
    message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_no_forwards_the_photo_file_id_from_state(memory_storage, monkeypatch):
    """Clicking NO after a screenshot question passes photo_file_id through to escalation."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)
    user = MagicMock(spec=User, id=6, username="dana", first_name="Dana")
    state = make_fsm_context(memory_storage, 6, 6)
    await state.update_data(
        last_question="Capture d'écran envoyée sans description.",
        last_answer="Je n'ai pas trouvé de réponse...",
        last_photo_file_id="screenshot_123",
    )

    cb_message = MagicMock(spec=Message)
    cb_message.text = "..."
    cb_message.edit_text = AsyncMock()
    callback = MagicMock(spec=CallbackQuery, id="cb1", from_user=user, data="resolve:no:0", message=cb_message)
    callback.answer = AsyncMock()

    client = AsyncMock()
    client.create_ticket.return_value = {"id": 42, "user_id": 6, "status": "OPEN"}
    bot = AsyncMock()
    bot.send_message.return_value = MagicMock(message_id=999)

    await handle_resolve_no(callback, state, bot=bot, backend_client=client)

    bot.send_photo.assert_called_once()
    assert bot.send_photo.call_args.kwargs["photo"] == "screenshot_123"


@pytest.mark.asyncio
async def test_resolve_no_without_a_screenshot_never_sends_a_photo(memory_storage, monkeypatch):
    """A plain text question (no photo in state) must not regress into an unwanted send_photo call."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)
    user = MagicMock(spec=User, id=7, username="erik", first_name="Erik")
    state = make_fsm_context(memory_storage, 7, 7)
    await state.update_data(last_question="Comment ça marche ?", last_answer="Voici comment.")

    cb_message = MagicMock(spec=Message)
    cb_message.text = "..."
    cb_message.edit_text = AsyncMock()
    callback = MagicMock(spec=CallbackQuery, id="cb2", from_user=user, data="resolve:no:0", message=cb_message)
    callback.answer = AsyncMock()

    client = AsyncMock()
    client.create_ticket.return_value = {"id": 43, "user_id": 7, "status": "OPEN"}
    bot = AsyncMock()
    bot.send_message.return_value = MagicMock(message_id=1000)

    await handle_resolve_no(callback, state, bot=bot, backend_client=client)

    bot.send_photo.assert_not_called()


# ---------------------------------------------------------------------------
# Community group
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def configure_community_group(monkeypatch):
    async def fake_get_community_group_id(backend_client=None):
        return COMMUNITY_GROUP_ID

    monkeypatch.setattr("bot.group_scope.get_community_group_id", fake_get_community_group_id)
    community_handlers._recent_bot_messages.clear()
    yield
    community_handlers._recent_bot_messages.clear()
    for task in list(getattr(community_handlers, "_background_tasks", ())):
        task.cancel()


@pytest.mark.asyncio
async def test_community_photo_outside_the_community_group_is_ignored(memory_storage):
    message = make_group_photo_message(chat_id=-999999, user_id=1, caption="un problème")
    state = make_fsm_context(memory_storage, 1, -999999)
    client = AsyncMock()

    await handle_community_photo_question(message, state, bot=AsyncMock(), backend_client=client)

    client.query.assert_not_called()
    message.answer.assert_not_called()


@pytest.mark.asyncio
async def test_community_photo_with_caption_is_answered_in_the_group(memory_storage):
    message = make_group_photo_message(chat_id=COMMUNITY_GROUP_ID, user_id=8, caption="reset mdp ?")
    state = make_fsm_context(memory_storage, 8, COMMUNITY_GROUP_ID)
    client = AsyncMock()
    client.query.return_value = {"found": True, "answer": "Cliquez sur mot de passe oublié."}
    sent_message = MagicMock(message_id=777)
    message.answer.return_value = sent_message

    await handle_community_photo_question(message, state, bot=AsyncMock(), backend_client=client)

    client.query.assert_called_once_with(query="reset mdp ?", user_id=8, user_handle="alice")
    data = await state.get_data()
    assert data["last_photo_file_id"] == "full_res_file_id"
    assert 777 in community_handlers._recent_bot_messages[COMMUNITY_GROUP_ID]


@pytest.mark.asyncio
async def test_community_photo_without_caption_uses_a_placeholder_question(memory_storage):
    message = make_group_photo_message(chat_id=COMMUNITY_GROUP_ID, user_id=9, caption=None)
    state = make_fsm_context(memory_storage, 9, COMMUNITY_GROUP_ID)
    client = AsyncMock()
    client.query.return_value = {"found": False, "answer": "Pas de réponse trouvée."}
    message.answer.return_value = MagicMock(message_id=778)

    await handle_community_photo_question(message, state, bot=AsyncMock(), backend_client=client)

    question_sent = client.query.call_args.kwargs["query"]
    assert question_sent
    data = await state.get_data()
    assert data["last_question"] == question_sent


@pytest.mark.asyncio
async def test_community_resolve_no_forwards_the_photo_file_id(memory_storage, monkeypatch):
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)
    state = make_fsm_context(memory_storage, 10, COMMUNITY_GROUP_ID)
    await state.update_data(
        last_question="Capture d'écran envoyée sans description.",
        last_answer="Pas de réponse.",
        last_answer_timestamp=__import__("time").time(),
        last_answer_message_id=555,
        asking_user_handle="fiona",
        last_photo_file_id="community_screenshot_id",
    )

    cb_message = MagicMock(spec=Message)
    cb_message.text = "..."
    cb_message.edit_text = AsyncMock()
    user = MagicMock(spec=User, id=10, username="fiona", first_name="Fiona")
    callback = MagicMock(spec=CallbackQuery, id="cb3", from_user=user, data="cresolve:no", message=cb_message)
    callback.answer = AsyncMock()

    client = AsyncMock()
    client.create_ticket.return_value = {"id": 44, "user_id": 10, "status": "OPEN"}
    bot = AsyncMock()
    bot.send_message.return_value = MagicMock(message_id=1001)

    await handle_community_resolve_no(callback, state, bot=bot, backend_client=client)

    bot.send_photo.assert_called_once()
    assert bot.send_photo.call_args.kwargs["photo"] == "community_screenshot_id"


# ---------------------------------------------------------------------------
# create_ticket_and_notify_admin_group: the shared photo-forwarding step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_ticket_forwards_the_screenshot_after_the_card(monkeypatch):
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100777888)
    client = AsyncMock(spec=BackendClient)
    client.create_ticket.return_value = {"id": 50}
    bot = AsyncMock()
    bot.send_message.return_value = MagicMock(message_id=2000)

    ticket = await create_ticket_and_notify_admin_group(
        client=client, bot=bot, user_id=1, user_handle="alice",
        question="q", automated_answer="a", photo_file_id="the_photo",
    )

    assert ticket["id"] == 50
    bot.send_photo.assert_called_once_with(
        chat_id=-100777888, photo="the_photo", caption=bot.send_photo.call_args.kwargs["caption"],
    )
    assert "50" in bot.send_photo.call_args.kwargs["caption"]


@pytest.mark.asyncio
async def test_create_ticket_sends_no_photo_when_none_is_given(monkeypatch):
    """Regression guard: the existing text-only flow must not start sending photos."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100777888)
    client = AsyncMock(spec=BackendClient)
    client.create_ticket.return_value = {"id": 51}
    bot = AsyncMock()
    bot.send_message.return_value = MagicMock(message_id=2001)

    await create_ticket_and_notify_admin_group(
        client=client, bot=bot, user_id=1, user_handle="alice", question="q", automated_answer="a",
    )

    bot.send_photo.assert_not_called()


@pytest.mark.asyncio
async def test_create_ticket_photo_send_failure_does_not_fail_ticket_creation(monkeypatch, caplog):
    """Best effort, like the card send itself: a Telegram error while sending the photo is swallowed."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100777888)
    client = AsyncMock(spec=BackendClient)
    client.create_ticket.return_value = {"id": 52}
    bot = AsyncMock()
    bot.send_message.return_value = MagicMock(message_id=2002)
    bot.send_photo.side_effect = Exception("file too large")

    ticket = await create_ticket_and_notify_admin_group(
        client=client, bot=bot, user_id=1, user_handle="alice",
        question="q", automated_answer="a", photo_file_id="the_photo",
    )

    assert ticket["id"] == 52


@pytest.mark.asyncio
async def test_create_ticket_never_sends_a_photo_when_the_support_group_is_not_configured(monkeypatch):
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", 0)
    client = AsyncMock(spec=BackendClient)
    client.create_ticket.return_value = {"id": 53}
    bot = AsyncMock()

    await create_ticket_and_notify_admin_group(
        client=client, bot=bot, user_id=1, user_handle="alice",
        question="q", automated_answer="a", photo_file_id="the_photo",
    )

    bot.send_photo.assert_not_called()
