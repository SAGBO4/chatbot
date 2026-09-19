"""Places that build Markdown from untrusted text must survive Telegram rejecting it."""
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Message, User

from app.config import settings
from bot.handlers.user_handlers import handle_resolve_no, handle_resolve_yes, handle_user_query
from bot.ticket_escalation import create_ticket_and_notify_admin_group


def make_state(user_id=5):
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=user_id, user_id=user_id))


def is_markdown(call):
    return call.kwargs.get("parse_mode") == "Markdown"


def make_callback(text="previous answer"):
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=User, id=5, username="alice", first_name="Alice")
    callback.message = MagicMock(spec=Message, text=text)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


@pytest.mark.asyncio
async def test_private_answer_is_resent_as_plain_text_when_the_markdown_is_rejected():
    message = MagicMock(spec=Message)
    message.text = "question"
    message.from_user = MagicMock(spec=User, id=5, username="alice", first_name="Alice")
    message.answer = AsyncMock(side_effect=[Exception("can't parse entities"), None])
    client = AsyncMock()
    client.query.return_value = {"answer": "answer with _an underscore"}

    await handle_user_query(message, make_state(), backend_client=client)

    first, second = message.answer.await_args_list
    assert is_markdown(first) and not is_markdown(second)
    assert second.args == first.args and "reply_markup" in second.kwargs


@pytest.mark.asyncio
async def test_resolve_yes_survives_both_edits_failing():
    callback = make_callback()
    callback.message.edit_text = AsyncMock(side_effect=[Exception("markdown"), Exception("message deleted")])

    await handle_resolve_yes(callback, make_state(), backend_client=AsyncMock())  # must not raise

    first, second = callback.message.edit_text.await_args_list
    assert is_markdown(first) and not is_markdown(second)


@pytest.mark.asyncio
async def test_resolve_no_edits_as_plain_text_after_the_ticket_is_created():
    state = make_state()
    await state.update_data(last_question="Why?", last_answer="Because.")
    callback = make_callback()
    callback.message.edit_text = AsyncMock(side_effect=[Exception("markdown"), None])
    client = AsyncMock()
    client.create_ticket.return_value = {"id": 9}

    await handle_resolve_no(callback, state, bot=AsyncMock(), backend_client=client)

    client.create_ticket.assert_called_once()
    first, second = callback.message.edit_text.await_args_list
    assert is_markdown(first) and not is_markdown(second)


@pytest.mark.asyncio
async def test_support_group_card_is_resent_as_a_plain_card(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", -100123)
    client = AsyncMock()
    client.create_ticket.return_value = {"id": 7}
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=[Exception("can't parse entities"), MagicMock(message_id=444)])

    ticket = await create_ticket_and_notify_admin_group(client, bot, 5, "al_ice", "Why?", "Because.")

    first, second = bot.send_message.await_args_list
    assert is_markdown(first) and "**" in first.kwargs["text"]
    assert not is_markdown(second) and "**" not in second.kwargs["text"] and "NOUVEAU TICKET SUPPORT #7" in second.kwargs["text"]
    client.attach_support_card.assert_awaited_once_with(ticket_id=7, message_id=444)
    assert ticket == {"id": 7}


@pytest.mark.asyncio
async def test_ticket_is_still_returned_when_the_group_card_cannot_be_sent_at_all(monkeypatch, caplog):
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", -100123)
    client = AsyncMock()
    client.create_ticket.return_value = {"id": 7}
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=Exception("chat not found"))

    with caplog.at_level(logging.ERROR):
        ticket = await create_ticket_and_notify_admin_group(client, bot, 5, "alice", "Why?", "Because.")

    assert ticket == {"id": 7}
    client.attach_support_card.assert_not_called()
    assert "Support group card failed in plain text too" in caplog.text
