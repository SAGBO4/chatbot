import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import User, Chat, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from bot.handlers.user_handlers import (
    handle_start,
    handle_user_query,
    handle_resolve_yes,
    handle_resolve_no,
)
from bot.handlers.support_handlers import handle_support_agent_reply
import logging
from aiogram.types import Voice
from app.config import settings
from bot.handlers.user_handlers import handle_help, UserQueryState
from bot.api_client import BackendClient


@pytest.fixture
def memory_storage():
    return MemoryStorage()


def make_fsm_context(storage: MemoryStorage, user_id: int, chat_id: int) -> FSMContext:
    key = StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


@pytest.mark.asyncio
async def test_bot_start_handler(memory_storage):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=123, type="private")
    message.from_user = MagicMock(spec=User, id=123, username="jean_test", first_name="Jean")
    message.text = "/start"
    message.answer = AsyncMock()

    state = make_fsm_context(memory_storage, 123, 123)

    await handle_start(message, state)
    message.answer.assert_called_once()
    assert "bienvenue" in message.answer.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_bot_user_query_and_resolution_flow(memory_storage):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=456, type="private")
    message.from_user = MagicMock(spec=User, id=456, username="claire_456", first_name="Claire")
    message.text = "Comment modifier mon mot de passe ?"
    message.answer = AsyncMock()

    state = make_fsm_context(memory_storage, 456, 456)

    mock_client = AsyncMock()
    mock_client.query.return_value = {
        "found": True,
        "answer": "Cliquez sur 'Mot de passe oublié' sur la page de connexion.",
    }

    # 1. User sends question
    await handle_user_query(message, state, backend_client=mock_client)
    message.answer.assert_called_once()
    assert "Cliquez sur 'Mot de passe oublié'" in message.answer.call_args[0][0]
    assert "Votre problème est-il résolu ?" in message.answer.call_args[0][0]

    # Check state data saved
    state_data = await state.get_data()
    assert state_data["last_question"] == "Comment modifier mon mot de passe ?"

    # 2. User confirms with OUI
    cb_message = MagicMock(spec=Message)
    cb_message.text = message.answer.call_args[0][0]
    cb_message.edit_text = AsyncMock()

    callback_yes = MagicMock(spec=CallbackQuery)
    callback_yes.id = "cb_yes_1"
    callback_yes.from_user = message.from_user
    callback_yes.data = "resolve:yes:0"
    callback_yes.message = cb_message
    callback_yes.answer = AsyncMock()

    await handle_resolve_yes(callback_yes, state)
    cb_message.edit_text.assert_called_once()
    assert "Problème résolu" in cb_message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_bot_resolution_no_escalates_to_group(memory_storage, monkeypatch):
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    user = MagicMock(spec=User, id=789, username="marc789", first_name="Marc")
    state = make_fsm_context(memory_storage, 789, 789)
    await state.update_data(
        last_question="Erreur de synchronisation cloud",
        last_answer="Aucune solution trouvée",
    )

    cb_message = MagicMock(spec=Message)
    cb_message.text = "Réponse précédente..."
    cb_message.edit_text = AsyncMock()

    callback_no = MagicMock(spec=CallbackQuery)
    callback_no.id = "cb_no_1"
    callback_no.from_user = user
    callback_no.data = "resolve:no:0"
    callback_no.message = cb_message
    callback_no.answer = AsyncMock()

    mock_client = AsyncMock()
    mock_client.create_ticket.return_value = {
        "id": 101,
        "user_id": 789,
        "status": "OPEN",
    }

    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = MagicMock(message_id=555)

    await handle_resolve_no(callback_no, state, bot=mock_bot, backend_client=mock_client)

    # Verifies ticket created
    mock_client.create_ticket.assert_called_once_with(
        user_id=789,
        user_handle="marc789",
        question="Erreur de synchronisation cloud",
        automated_answer="Aucune solution trouvée",
    )
    # Verifies user message updated with ticket ID
    assert "Ticket #101" in cb_message.edit_text.call_args[0][0]

    # Verifies support group card sent
    mock_bot.send_message.assert_called_once()
    group_card_text = mock_bot.send_message.call_args.kwargs["text"]
    assert "NOUVEAU TICKET SUPPORT #101" in group_card_text
    assert "@marc789" in group_card_text

    # Verifies the card's Telegram message id is recorded against the ticket
    mock_client.attach_support_card.assert_called_once_with(
        ticket_id=101, message_id=555
    )


@pytest.mark.asyncio
async def test_support_agent_reply_handler_resolves_by_message_id(monkeypatch):
    """Primary path: the reply is resolved via the replied-to message's identity,
    without needing the card's text to match the regex pattern at all."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555
    # Deliberately does NOT match TICKET_ID_REGEX/USER_ID_REGEX, to prove the
    # id-based lookup is what resolves the ticket, not the text fallback.
    replied_card.text = "Cette carte a été reformulée sans le format attendu."

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 51
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Veuillez redémarrer le daemon de synchronisation via systemctl restart sync-daemon."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_bot = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 101,
        "user_id": 789,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 101,
        "user_id": 789,
        "status": "RESOLVED",
        "solution": agent_message.text,
    }

    await handle_support_agent_reply(
        agent_message, bot=mock_bot, backend_client=mock_client
    )

    # 0. Looked up by the replied-to message's identity
    mock_client.get_ticket_by_support_message.assert_called_once_with(555)

    # 1. Backend resolve_ticket called with solution and agent
    mock_client.resolve_ticket.assert_called_once_with(
        ticket_id=101,
        solution=agent_message.text,
        resolved_by="agent_sophie",
        add_to_knowledge_base=True,
    )

    # 2. Bot sent solution to original user
    mock_bot.send_message.assert_called_once()
    user_msg = mock_bot.send_message.call_args.kwargs["text"]
    assert mock_bot.send_message.call_args.kwargs["chat_id"] == 789
    assert "systemctl restart sync-daemon" in user_msg

    # 3. Agent reply confirmed in group
    agent_message.reply.assert_called_once()
    assert "Ticket #101 résolu" in agent_message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_support_agent_reply_notifies_both_user_and_community_group(monkeypatch):
    """When a ticket originated in a community group, resolving it notifies both the user inbox AND the group."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555
    replied_card.text = "🚨 NOUVEAU TICKET SUPPORT #102\n👤 Utilisateur : @marc789 (ID: 789)\n❓ Question : Erreur sync"
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 52
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Voici la solution officielle."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 102,
        "user_id": 789,
        "user_handle": "marc789",
        "source_chat_id": -100555666,
        "source_message_id": 444,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 102,
        "user_id": 789,
        "user_handle": "marc789",
        "status": "RESOLVED",
        "is_newly_resolved": True,
        "source_chat_id": -100555666,
        "source_message_id": 444,
    }

    await handle_support_agent_reply(
        agent_message, bot=mock_bot, backend_client=mock_client
    )

    # 1. Backend resolve_ticket called
    mock_client.resolve_ticket.assert_called_once()

    # 2. Bot sent 2 messages: 1 to user DM, 1 to community group
    assert mock_bot.send_message.call_count == 2
    calls = mock_bot.send_message.call_args_list

    # First call: private user DM
    assert calls[0].kwargs["chat_id"] == 789
    assert "Voici la solution officielle" in calls[0].kwargs["text"]

    # Second call: community group with reply_to_message_id
    assert calls[1].kwargs["chat_id"] == -100555666
    assert calls[1].kwargs["reply_to_message_id"] == 444
    assert "@marc789" in calls[1].kwargs["text"]
    assert "Voici la solution officielle" in calls[1].kwargs["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_source_chat_id",
    [
        None,             # Absent source_chat_id (opened in private)
        789,              # Equals user_id (private chat)
        999999,           # Another positive user ID (must never be treated as group)
        -100999888,       # Matches the support group itself (settings.TELEGRAM_SUPPORT_GROUP_ID)
    ],
)
async def test_support_agent_reply_privacy_never_broadcasts_to_group(invalid_source_chat_id, monkeypatch):
    """
    Absolute privacy guarantee:
    If source_chat_id is absent, equals user_id, is positive (private chat), or matches
    the support group itself, NO group message is ever sent. Only the private user DM is delivered.
    """
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555
    replied_card.text = "🚨 NOUVEAU TICKET SUPPORT #103\n👤 Utilisateur : @marc789 (ID: 789)\n❓ Question : Secret query"
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 53
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Private solution only."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 103,
        "user_id": 789,
        "user_handle": "marc789",
        "source_chat_id": invalid_source_chat_id,
        "source_message_id": 123 if invalid_source_chat_id else None,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 103,
        "user_id": 789,
        "user_handle": "marc789",
        "status": "RESOLVED",
        "is_newly_resolved": True,
        "source_chat_id": invalid_source_chat_id,
        "source_message_id": 123 if invalid_source_chat_id else None,
    }

    await handle_support_agent_reply(
        agent_message, bot=mock_bot, backend_client=mock_client
    )

    # Exactly 1 message sent: ONLY to the private user DM (chat_id=789)
    assert mock_bot.send_message.call_count == 1
    call = mock_bot.send_message.call_args
    assert call.kwargs["chat_id"] == 789
    assert "Private solution only" in call.kwargs["text"]

    # Resolution confirmed to agent in the support group
    agent_message.reply.assert_called_once()
    assert "Ticket #103 résolu" in agent_message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_support_agent_reply_fallback_when_source_message_deleted_in_group(monkeypatch):
    """
    Robustness test:
    When the question message in the community group was deleted before the ticket was resolved,
    replying to source_message_id fails. The handler must catch the failure and post unattached
    to the community group without breaking ticket resolution.
    """
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555
    replied_card.text = "🚨 NOUVEAU TICKET SUPPORT #104\n👤 Utilisateur : @marc789 (ID: 789)\n❓ Question : Erreur sync"
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 54
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Solution pour message supprimé."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 104,
        "user_id": 789,
        "user_handle": "marc789",
        "source_chat_id": -100555666,
        "source_message_id": 999,  # Message deleted in Telegram
    }
    mock_client.resolve_ticket.return_value = {
        "id": 104,
        "user_id": 789,
        "user_handle": "marc789",
        "status": "RESOLVED",
        "is_newly_resolved": True,
        "source_chat_id": -100555666,
        "source_message_id": 999,
    }

    # Simulate bot.send_message:
    # 1. User DM -> succeeds
    # 2. Community group with reply_to_message_id=999 -> fails (message deleted)
    # 3. Community group unattached fallback -> succeeds
    async def mock_send_message(*args, **kwargs):
        if kwargs.get("reply_to_message_id") == 999:
            raise Exception("Bad Request: message to be replied not found")
        return MagicMock(message_id=12345)

    mock_bot.send_message = AsyncMock(side_effect=mock_send_message)

    await handle_support_agent_reply(
        agent_message, bot=mock_bot, backend_client=mock_client
    )

    # 1. Private DM sent
    # 2. Group call with reply_to_message_id attempted (failed in Markdown and plain text)
    # 3. Unattached group fallback succeeded
    calls = mock_bot.send_message.call_args_list
    assert len(calls) >= 3

    # First call: private user DM
    assert calls[0].kwargs["chat_id"] == 789
    assert "Solution pour message supprimé" in calls[0].kwargs["text"]

    # Final call: unattached message to community group (no reply_to_message_id)
    last_call = calls[-1]
    assert last_call.kwargs["chat_id"] == -100555666
    assert "reply_to_message_id" not in last_call.kwargs
    assert "@marc789" in last_call.kwargs["text"]
    assert "Solution pour message supprimé" in last_call.kwargs["text"]

    # Ticket resolution still confirmed in support group
    agent_message.reply.assert_called_once()
    assert "Ticket #104 résolu" in agent_message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_support_agent_reply_community_group_without_source_message_id(monkeypatch):
    """When source_message_id is None, message is sent unattached to the community group directly."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555
    replied_card.text = "🚨 NOUVEAU TICKET SUPPORT #105\n👤 Utilisateur : @marc789 (ID: 789)\n❓ Question : Question sans msg id"
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 55
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Solution directe."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 105,
        "user_id": 789,
        "user_handle": "marc789",
        "source_chat_id": -100555666,
        "source_message_id": None,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 105,
        "user_id": 789,
        "user_handle": "marc789",
        "status": "RESOLVED",
        "is_newly_resolved": True,
        "source_chat_id": -100555666,
        "source_message_id": None,
    }

    await handle_support_agent_reply(
        agent_message, bot=mock_bot, backend_client=mock_client
    )

    assert mock_bot.send_message.call_count == 2
    calls = mock_bot.send_message.call_args_list

    # User DM
    assert calls[0].kwargs["chat_id"] == 789

    # Community group unattached
    assert calls[1].kwargs["chat_id"] == -100555666
    assert "reply_to_message_id" not in calls[1].kwargs
    assert "@marc789" in calls[1].kwargs["text"]


@pytest.mark.asyncio
async def test_support_agent_reply_user_dm_failure_still_notifies_community_group(monkeypatch):
    """If delivering to user DM fails (e.g. user blocked bot), community group reply still succeeds."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555
    replied_card.text = "🚨 NOUVEAU TICKET SUPPORT #106\n👤 Utilisateur : @marc789 (ID: 789)\n❓ Question : Test block"
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 56
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Solution avec user bloqué."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 106,
        "user_id": 789,
        "user_handle": "marc789",
        "source_chat_id": -100555666,
        "source_message_id": 333,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 106,
        "user_id": 789,
        "user_handle": "marc789",
        "status": "RESOLVED",
        "is_newly_resolved": True,
        "source_chat_id": -100555666,
        "source_message_id": 333,
    }

    async def mock_send_message(*args, **kwargs):
        if kwargs.get("chat_id") == 789:
            raise Exception("Bot was blocked by the user")
        return MagicMock(message_id=999)

    mock_bot.send_message = AsyncMock(side_effect=mock_send_message)

    await handle_support_agent_reply(
        agent_message, bot=mock_bot, backend_client=mock_client
    )

    # Community group still received the notification
    community_calls = [c for c in mock_bot.send_message.call_args_list if c.kwargs.get("chat_id") == -100555666]
    assert len(community_calls) == 1
    assert community_calls[0].kwargs["reply_to_message_id"] == 333
    assert "Solution avec user bloqué" in community_calls[0].kwargs["text"]


@pytest.mark.asyncio
async def test_support_agent_reply_falls_back_to_text_when_id_lookup_misses(monkeypatch):
    """When the id-based lookup finds nothing (e.g. a ticket created before this
    mechanism existed), the previous text-parsing behavior still resolves it."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42  # the bot's own Telegram id, used to prove the card came from it

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555
    replied_card.text = "🚨 NOUVEAU TICKET SUPPORT #101\n👤 Utilisateur : @marc789 (ID: 789)\n❓ Question : Erreur sync"
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 51
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Veuillez redémarrer le daemon de synchronisation via systemctl restart sync-daemon."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = None
    mock_client.resolve_ticket.return_value = {
        "id": 101,
        "user_id": 789,
        "status": "RESOLVED",
        "solution": agent_message.text,
    }

    await handle_support_agent_reply(
        agent_message, bot=mock_bot, backend_client=mock_client
    )

    mock_client.resolve_ticket.assert_called_once_with(
        ticket_id=101,
        solution=agent_message.text,
        resolved_by="agent_sophie",
        add_to_knowledge_base=True,
    )
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args.kwargs["chat_id"] == 789
    agent_message.reply.assert_called_once()
    assert "Ticket #101 résolu" in agent_message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_support_agent_reply_text_fallback_ignored_when_replied_message_not_from_bot(monkeypatch):
    """
    Security regression test: the text-parsing fallback must only ever be
    trusted for a card the bot itself posted. A message forged by a third
    party (or another admin's unrelated message) that merely happens to
    contain "TICKET #<n> ID: <n>" must never be parsed as a real ticket
    card, even by a genuine group admin replying to it.
    """
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    forged_card = MagicMock(spec=Message)
    forged_card.message_id = 777
    forged_card.text = "TICKET #101 ID: 789"
    # Posted by some other group member, NOT the bot.
    forged_card.from_user = MagicMock(spec=User, id=555)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 51
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Envoyez vos clés privées à ce lien : https://phishing.example"
    agent_message.reply_to_message = forged_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = None

    await handle_support_agent_reply(
        agent_message, bot=mock_bot, backend_client=mock_client
    )

    mock_client.resolve_ticket.assert_not_called()
    mock_bot.send_message.assert_not_called()
    agent_message.reply.assert_called_once()
    assert "n'ai pas pu associer" in agent_message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_support_agent_reply_rejected_for_non_admin_group_member(monkeypatch):
    """
    Security regression test: being physically in the support group is not
    enough - a non-admin member replying to a real ticket card must be
    ignored, never resolve the ticket or message the user on the team's
    behalf.
    """
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)
    monkeypatch.setattr(
        "bot.handlers.support_handlers.is_bot_admin",
        AsyncMock(return_value=False),
    )

    member_user = MagicMock(spec=User, id=555, username="random_member", first_name="Random", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    real_card = MagicMock(spec=Message)
    real_card.message_id = 555
    real_card.text = "🚨 NOUVEAU TICKET SUPPORT #101\n👤 Utilisateur : @marc789 (ID: 789)\n❓ Question : Erreur sync"

    member_message = MagicMock(spec=Message)
    member_message.message_id = 51
    member_message.chat = group_chat
    member_message.from_user = member_user
    member_message.text = "Envoyez vos clés privées ici : https://phishing.example"
    member_message.reply_to_message = real_card
    member_message.reply = AsyncMock()

    mock_bot = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {"id": 101, "user_id": 789}

    await handle_support_agent_reply(
        member_message, bot=mock_bot, backend_client=mock_client
    )

    mock_client.resolve_ticket.assert_not_called()
    mock_bot.send_message.assert_not_called()
    member_message.reply.assert_not_called()


@pytest.mark.asyncio
async def test_support_agent_reply_no_match_replies_with_explicit_notice(monkeypatch):
    """When neither the id-based lookup nor the text fallback identify a
    ticket, the bot must not resolve anything and must say so explicitly."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 999
    replied_card.text = "Un message quelconque du groupe, sans rapport avec un ticket."

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 51
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Une réponse sans rapport."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_bot = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = None

    await handle_support_agent_reply(
        agent_message, bot=mock_bot, backend_client=mock_client
    )

    mock_client.resolve_ticket.assert_not_called()
    mock_bot.send_message.assert_not_called()
    agent_message.reply.assert_called_once()
    assert "n'ai pas pu associer" in agent_message.reply.call_args[0][0]


def _make_support_agent_message(group_chat, agent_user, replied_card):
    """A MagicMock(spec=Message) with every non-text media field defaulted to
    None, like a real aiogram Message where only one content type is set."""
    message = MagicMock(spec=Message)
    message.message_id = 51
    message.chat = group_chat
    message.from_user = agent_user
    message.reply_to_message = replied_card
    message.reply = AsyncMock()
    message.text = None
    message.caption = None
    message.photo = None
    message.sticker = None
    message.voice = None
    message.audio = None
    message.video = None
    message.animation = None
    return message


@pytest.mark.asyncio
async def test_support_agent_reply_media_without_caption_asks_for_text(monkeypatch):
    """A photo/sticker/voice reply with no usable text must not crash
    (message.text is None for media) and must not resolve the ticket."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")
    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555

    agent_message = _make_support_agent_message(group_chat, agent_user, replied_card)
    agent_message.sticker = MagicMock()  # e.g. a sticker reply, no caption possible

    mock_bot = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {"id": 101, "user_id": 789}

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    mock_client.resolve_ticket.assert_not_called()
    agent_message.reply.assert_called_once()
    assert "texte" in agent_message.reply.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_support_agent_reply_photo_with_caption_resolves_ticket(monkeypatch):
    """A photo (e.g. a screenshot) with a caption uses the caption as the
    solution, instead of crashing or being discarded."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")
    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555

    agent_message = _make_support_agent_message(group_chat, agent_user, replied_card)
    agent_message.photo = [MagicMock()]
    agent_message.caption = "Voici une capture d'écran : redémarrez l'application."

    mock_bot = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {"id": 101, "user_id": 789}
    mock_client.resolve_ticket.return_value = {"id": 101, "user_id": 789, "status": "RESOLVED"}

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    mock_client.resolve_ticket.assert_called_once_with(
        ticket_id=101,
        solution="Voici une capture d'écran : redémarrez l'application.",
        resolved_by="agent_sophie",
        add_to_knowledge_base=True,
    )


@pytest.mark.asyncio
async def test_support_agent_reply_voice_transcribed_via_whisper(monkeypatch):
    """A voice reply is transcribed via OpenAI Whisper when AI_PROVIDER=openai,
    then used as the ticket solution."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)
    monkeypatch.setattr("app.config.settings.AI_PROVIDER", "openai")
    monkeypatch.setattr("app.config.settings.AI_API_KEY", "sk-test-key")

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")
    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555

    agent_message = _make_support_agent_message(group_chat, agent_user, replied_card)
    agent_message.voice = MagicMock(file_id="voice123", file_size=1000)

    mock_bot = AsyncMock()
    mock_bot.get_file.return_value = MagicMock(file_path="voice/file_123.oga")
    audio_buffer = MagicMock()
    audio_buffer.read.return_value = b"fake-ogg-bytes"
    mock_bot.download_file.return_value = audio_buffer

    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {"id": 101, "user_id": 789}
    mock_client.resolve_ticket.return_value = {"id": 101, "user_id": 789, "status": "RESOLVED"}

    mock_whisper_response = MagicMock(status_code=200)
    mock_whisper_response.json.return_value = {"text": "Redémarrez le daemon de synchronisation."}

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_whisper_response)):
        await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    mock_bot.get_file.assert_called_once_with("voice123")
    mock_client.resolve_ticket.assert_called_once_with(
        ticket_id=101,
        solution="Redémarrez le daemon de synchronisation.",
        resolved_by="agent_sophie",
        add_to_knowledge_base=True,
    )


@pytest.mark.asyncio
async def test_support_agent_reply_voice_without_openai_asks_for_text(monkeypatch):
    """Without AI_PROVIDER=openai, a voice reply cannot be transcribed - the
    handler must ask for text instead of crashing or silently failing."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)
    monkeypatch.setattr("app.config.settings.AI_PROVIDER", "gemini")
    monkeypatch.setattr("app.config.settings.AI_API_KEY", None)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")
    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555

    agent_message = _make_support_agent_message(group_chat, agent_user, replied_card)
    agent_message.voice = MagicMock(file_id="voice123", file_size=1000)

    mock_bot = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {"id": 101, "user_id": 789}

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    mock_bot.get_file.assert_not_called()
    mock_client.resolve_ticket.assert_not_called()
    agent_message.reply.assert_called_once()
    assert "texte" in agent_message.reply.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_support_agent_reply_ignored_from_private_chat(monkeypatch):
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    attacker_user = MagicMock(spec=User, id=789, username="attacker", first_name="Eve", last_name=None)
    # The attacker DMs the bot: private chat id equals their own user id, as Telegram does.
    private_chat = MagicMock(spec=Chat, id=789, type="private")

    forged_card = MagicMock(spec=Message)
    forged_card.text = "🚨 NOUVEAU TICKET SUPPORT #101\n👤 Utilisateur : @marc789 (ID: 789)\n❓ Question : Erreur sync"

    attacker_message = MagicMock(spec=Message)
    attacker_message.message_id = 51
    attacker_message.chat = private_chat
    attacker_message.from_user = attacker_user
    attacker_message.text = "Solution forgée par l'attaquant"
    attacker_message.reply_to_message = forged_card
    attacker_message.reply = AsyncMock()

    mock_bot = AsyncMock()
    mock_client = AsyncMock()

    await handle_support_agent_reply(
        attacker_message, bot=mock_bot, backend_client=mock_client
    )

    # No ticket resolution, no message sent to any user, no group confirmation.
    mock_client.resolve_ticket.assert_not_called()
    mock_bot.send_message.assert_not_called()
    attacker_message.reply.assert_not_called()


@pytest.mark.asyncio
async def test_support_agent_reply_ignored_from_other_group(monkeypatch):
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    other_user = MagicMock(spec=User, id=111, username="not_an_agent", first_name="Bob", last_name=None)
    # A different group chat than the configured support group.
    other_group_chat = MagicMock(spec=Chat, id=-100111222, type="supergroup")

    forged_card = MagicMock(spec=Message)
    forged_card.text = "🚨 NOUVEAU TICKET SUPPORT #101\n👤 Utilisateur : @marc789 (ID: 789)\n❓ Question : Erreur sync"

    other_group_message = MagicMock(spec=Message)
    other_group_message.message_id = 52
    other_group_message.chat = other_group_chat
    other_group_message.from_user = other_user
    other_group_message.text = "Solution envoyée depuis un autre groupe"
    other_group_message.reply_to_message = forged_card
    other_group_message.reply = AsyncMock()

    mock_bot = AsyncMock()
    mock_client = AsyncMock()

    await handle_support_agent_reply(
        other_group_message, bot=mock_bot, backend_client=mock_client
    )

    mock_client.resolve_ticket.assert_not_called()
    mock_bot.send_message.assert_not_called()
    other_group_message.reply.assert_not_called()


@pytest.mark.asyncio
async def test_support_agent_reply_ignored_when_support_group_unconfigured(monkeypatch):
    # Default configuration: TELEGRAM_SUPPORT_GROUP_ID is unset (sentinel "0").
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", 0)

    user = MagicMock(spec=User, id=0, username="whoever", first_name="Whoever", last_name=None)
    # Chat id happens to be the same falsy sentinel value as the unconfigured setting.
    chat = MagicMock(spec=Chat, id=0, type="private")

    forged_card = MagicMock(spec=Message)
    forged_card.text = "🚨 NOUVEAU TICKET SUPPORT #101\n👤 Utilisateur : @marc789 (ID: 789)\n❓ Question : Erreur sync"

    message = MagicMock(spec=Message)
    message.message_id = 53
    message.chat = chat
    message.from_user = user
    message.text = "Tentative avec un groupe non configuré"
    message.reply_to_message = forged_card
    message.reply = AsyncMock()

    mock_bot = AsyncMock()
    mock_client = AsyncMock()

    await handle_support_agent_reply(
        message, bot=mock_bot, backend_client=mock_client
    )

    mock_client.resolve_ticket.assert_not_called()
    mock_bot.send_message.assert_not_called()
    message.reply.assert_not_called()


@pytest.mark.asyncio
async def test_support_agent_reply_escapes_markdown_in_solution_and_agent_name(monkeypatch):
    support_group_id = -100999888777
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", support_group_id)

    agent_user = MagicMock(spec=User, id=999, username="agent_007", first_name="Agent_007", last_name=None)
    chat = MagicMock(spec=Chat, id=support_group_id, type="supergroup")

    card = MagicMock(spec=Message, message_id=4001)
    message = MagicMock(
        spec=Message,
        message_id=4002,
        chat=chat,
        from_user=agent_user,
        text="Voici le lien: https://stackwallet.com/help_v2_faq et test *bold*.",
        reply_to_message=card,
    )
    message.reply = AsyncMock()

    mock_bot = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 15,
        "user_id": 888888,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 15,
        "user_id": 888888,
        "solution": "Voici le lien: https://stackwallet.com/help_v2_faq et test *bold*.",
    }

    await handle_support_agent_reply(message, bot=mock_bot, backend_client=mock_client)

    mock_bot.send_message.assert_called_once()
    sent_text = mock_bot.send_message.call_args.kwargs["text"]
    assert "agent\\_007" in sent_text
    assert "help\\_v2\\_faq" in sent_text
    assert "\\*bold\\*" in sent_text


@pytest.mark.asyncio
async def test_support_agent_reply_falls_back_to_plain_text_on_send_error(monkeypatch):
    support_group_id = -100999888777
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", support_group_id)

    agent_user = MagicMock(spec=User, id=999, username="agent_bob", first_name="Bob", last_name=None)
    chat = MagicMock(spec=Chat, id=support_group_id, type="supergroup")

    card = MagicMock(spec=Message, message_id=4001)
    message = MagicMock(
        spec=Message,
        message_id=4002,
        chat=chat,
        from_user=agent_user,
        text="Solution text here",
        reply_to_message=card,
    )
    message.reply = AsyncMock()

    mock_bot = AsyncMock()
    mock_bot.send_message.side_effect = [Exception("Bad Request: can't parse entities"), MagicMock()]
    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 20,
        "user_id": 55555,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 20,
        "user_id": 55555,
        "solution": "Solution text here",
    }

    await handle_support_agent_reply(message, bot=mock_bot, backend_client=mock_client)

    assert mock_bot.send_message.call_count == 2
    second_call_kwargs = mock_bot.send_message.call_args_list[1].kwargs
    assert "parse_mode" not in second_call_kwargs or second_call_kwargs["parse_mode"] is None
    assert "Solution text here" in second_call_kwargs["text"]


@pytest.mark.asyncio
async def test_handle_resolve_no_double_click_prevention(memory_storage):
    user = MagicMock(spec=User, id=444, username="clicker", first_name="Clicker")
    state = make_fsm_context(memory_storage, 444, 444)
    # State has no last_question (simulating second rapid click after first cleared it)
    await state.clear()

    cb_msg = MagicMock(spec=Message, text="Previous question answer")
    callback = MagicMock(spec=CallbackQuery, id="cb_double", from_user=user, data="resolve:no", message=cb_msg)
    callback.answer = AsyncMock()

    mock_client = AsyncMock()
    mock_bot = AsyncMock()

    await handle_resolve_no(callback, state, bot=mock_bot, backend_client=mock_client)

    # Verifies early return without creating ticket
    callback.answer.assert_called_once_with("Cette demande a déjà été prise en compte.", show_alert=False)
    mock_client.create_ticket.assert_not_called()
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_support_agent_reply_already_resolved_collision(monkeypatch):
    support_group_id = -100999888777
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", support_group_id)

    agent_user = MagicMock(spec=User, id=999, username="agent_late", first_name="Agent Late")
    chat = MagicMock(spec=Chat, id=support_group_id, type="supergroup")

    card = MagicMock(spec=Message, message_id=5001)
    message = MagicMock(
        spec=Message,
        message_id=5002,
        chat=chat,
        from_user=agent_user,
        text="Voici ma solution tardive.",
        reply_to_message=card,
    )
    message.reply = AsyncMock()

    mock_bot = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {"id": 33, "user_id": 1234}
    # Backend returns ticket with is_newly_resolved=False
    mock_client.resolve_ticket.return_value = {
        "id": 33,
        "user_id": 1234,
        "resolved_by": "first_agent",
        "is_newly_resolved": False,
    }

    await handle_support_agent_reply(message, bot=mock_bot, backend_client=mock_client)

    # Solution is NOT forwarded to user
    mock_bot.send_message.assert_not_called()
    # Agent receives explicit notice that ticket was already resolved
    message.reply.assert_called_once()
    reply_text = message.reply.call_args[0][0]
    assert "déjà résolu" in reply_text
    assert "first\\_agent" in reply_text


@pytest.mark.asyncio
async def test_handle_resolve_no_with_excessively_long_text_does_not_overflow_telegram_limit(memory_storage, monkeypatch):
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    user = MagicMock(spec=User, id=888, username="long_user", first_name="Long")
    state = make_fsm_context(memory_storage, 888, 888)
    huge_question = "Q" * 1500
    huge_answer = "A" * 3000
    await state.update_data(
        last_question=huge_question,
        last_answer=huge_answer,
    )

    cb_message = MagicMock(spec=Message)
    cb_message.text = "Réponse précédente..."
    cb_message.edit_text = AsyncMock()

    callback_no = MagicMock(spec=CallbackQuery)
    callback_no.id = "cb_long"
    callback_no.from_user = user
    callback_no.data = "resolve:no:0"
    callback_no.message = cb_message
    callback_no.answer = AsyncMock()

    mock_client = AsyncMock()
    mock_client.create_ticket.return_value = {
        "id": 999,
        "user_id": 888,
        "status": "OPEN",
    }

    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = MagicMock(message_id=777)

    await handle_resolve_no(callback_no, state, bot=mock_bot, backend_client=mock_client)

    mock_bot.send_message.assert_called_once()
    group_card_text = mock_bot.send_message.call_args.kwargs["text"]
    assert len(group_card_text) <= 4000
    assert "NOUVEAU TICKET SUPPORT #999" in group_card_text


@pytest.mark.asyncio
async def test_handle_resolve_no_proceeds_to_escalate_when_user_edit_text_fails(memory_storage, monkeypatch):
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    user = MagicMock(spec=User, id=777, username="edit_fail_user", first_name="User")
    state = make_fsm_context(memory_storage, 777, 777)
    await state.update_data(
        last_question="Question simple",
        last_answer="Réponse",
    )

    cb_message = MagicMock(spec=Message)
    cb_message.text = "Texte"
    cb_message.edit_text = AsyncMock(side_effect=Exception("Telegram entity parse error"))

    callback_no = MagicMock(spec=CallbackQuery)
    callback_no.id = "cb_fail"
    callback_no.from_user = user
    callback_no.data = "resolve:no:0"
    callback_no.message = cb_message
    callback_no.answer = AsyncMock()

    mock_client = AsyncMock()
    mock_client.create_ticket.return_value = {
        "id": 100,
        "user_id": 777,
        "status": "OPEN",
    }

    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = MagicMock(message_id=888)

    await handle_resolve_no(callback_no, state, bot=mock_bot, backend_client=mock_client)

    # Group card MUST be sent even if edit_text failed
    mock_bot.send_message.assert_called_once()
    assert "NOUVEAU TICKET SUPPORT #100" in mock_bot.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_support_agent_reply_with_excessively_long_solution_caps_user_notification(monkeypatch):
    support_group_id = -100999888
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", support_group_id)

    agent_user = MagicMock(spec=User, id=99, username="agent_long", first_name="Agent")
    group_chat = MagicMock(spec=Chat, id=support_group_id, type="supergroup")

    card = MagicMock(spec=Message, message_id=123)
    card.text = "TICKET SUPPORT #42"

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 124
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "S" * 4500
    agent_message.reply_to_message = card
    agent_message.reply = AsyncMock()

    mock_bot = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {"id": 42, "user_id": 999}
    mock_client.resolve_ticket.return_value = {
        "id": 42,
        "user_id": 999,
        "status": "RESOLVED",
        "solution": agent_message.text,
        "is_newly_resolved": True,
    }

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    mock_bot.send_message.assert_called_once()
    delivered_text = mock_bot.send_message.call_args.kwargs["text"]
    assert len(delivered_text) <= 4000
    assert "...(tronqué)" in delivered_text


@pytest.mark.asyncio
async def test_support_agent_reply_truncates_solution_exceeding_backend_limit(monkeypatch):
    """When an agent sends a solution > 5000 chars, it is truncated before calling backend resolve_ticket."""
    support_group_id = -100999888
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", support_group_id)

    agent_user = MagicMock(spec=User, id=99, username="agent_verbose", first_name="Agent")
    group_chat = MagicMock(spec=Chat, id=support_group_id, type="supergroup")

    card = MagicMock(spec=Message, message_id=123)
    card.text = "TICKET SUPPORT #42"

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 124
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "X" * 6000
    agent_message.reply_to_message = card
    agent_message.reply = AsyncMock()

    mock_bot = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_ticket_by_support_message.return_value = {"id": 42, "user_id": 999}
    mock_client.resolve_ticket.return_value = {
        "id": 42,
        "user_id": 999,
        "status": "RESOLVED",
        "solution": "capped",
        "is_newly_resolved": True,
    }

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    mock_client.resolve_ticket.assert_called_once()
    passed_solution = mock_client.resolve_ticket.call_args.kwargs["solution"]
    assert len(passed_solution) <= 5000
    assert "...(tronqué)" in passed_solution


@pytest.mark.asyncio
async def test_handle_user_query_rejects_questions_exceeding_telegram_limit():
    """Questions > 4096 characters are caught and warned before querying backend."""
    user = MagicMock(spec=User, id=123, username="user_alice", first_name="Alice")
    message = MagicMock(spec=Message)
    message.from_user = user
    message.text = "Q" * 4500
    message.answer = AsyncMock()

    state = AsyncMock()
    mock_client = AsyncMock()

    await handle_user_query(message, state=state, backend_client=mock_client)

    mock_client.query.assert_not_called()
    message.answer.assert_called_once()
    assert "trop longue" in message.answer.call_args[0][0]





@pytest.mark.parametrize("provider", ["openai", "OpenAI", " OPENAI "])
@pytest.mark.asyncio
async def test_voice_transcription_accepts_any_casing_of_the_openai_provider(monkeypatch, provider):
    """AIAssistantService lower-cases AI_PROVIDER, so AI_PROVIDER=OpenAI enables AI answers; speech-to-text must too."""
    from bot.handlers.support_handlers import _transcribe_voice_message

    monkeypatch.setattr("app.config.settings.AI_PROVIDER", provider)
    monkeypatch.setattr("app.config.settings.AI_API_KEY", "sk-test-key")
    message = MagicMock(spec=Message)
    message.voice = MagicMock(file_id="voice123", file_size=1000)
    message.audio = None
    mock_bot = AsyncMock()
    mock_bot.get_file.return_value = MagicMock(file_path="voice/file_123.oga")
    mock_bot.download_file.return_value = MagicMock(read=MagicMock(return_value=b"ogg"))
    response = MagicMock(status_code=200)
    response.json.return_value = {"text": "Redemarrez le service."}

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)):
        assert await _transcribe_voice_message(message, mock_bot) == "Redemarrez le service."


@pytest.mark.asyncio
async def test_already_resolved_notice_names_another_agent_in_english_when_the_name_is_missing(monkeypatch):
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)
    agent_user = MagicMock(spec=User, id=99, username="agent_late", first_name="Late", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")
    card = MagicMock(spec=Message)
    card.message_id = 555
    message = _make_support_agent_message(group_chat, agent_user, card)
    message.text = "A late solution."

    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"
    mock_client.get_ticket_by_support_message.return_value = {"id": 33, "user_id": 1234}
    mock_client.resolve_ticket.return_value = {"id": 33, "user_id": 1234, "resolved_by": None, "is_newly_resolved": False}

    await handle_support_agent_reply(message, bot=AsyncMock(), backend_client=mock_client)

    assert "another agent" in message.reply.call_args[0][0]


# ---------------------------------------------------------------------------
# Cases numbered 1 (functional), 2 (security) and 3 (robustness) in their docstrings
# ---------------------------------------------------------------------------


@pytest.fixture
def bot_test_env():
    storage = MemoryStorage()
    user = MagicMock(spec=User, id=1001, username="test_user", first_name="Test")
    user_chat = MagicMock(spec=Chat, id=1001, type="private")
    state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=1001, user_id=1001))
    mock_bot = AsyncMock()
    mock_backend_client = AsyncMock(spec=BackendClient)
    return {
        "user": user,
        "chat": user_chat,
        "state": state,
        "bot": mock_bot,
        "client": mock_backend_client,
    }


@pytest.mark.asyncio
async def test_bot_handlers_start_command_clears_state_and_sends_welcome(bot_test_env):
    """
    1. FUNCTIONAL:
    /start resets the FSM state and sends the welcome message.
    """
    state = bot_test_env["state"]
    await state.set_state(UserQueryState.waiting_for_resolution)

    message = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"])
    message.answer = AsyncMock()

    await handle_start(message, state)

    assert await state.get_state() is None
    message.answer.assert_called_once()
    assert "Bonjour et bienvenue" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_bot_handlers_start_in_group_presents_group_welcome(bot_test_env, monkeypatch):
    """/start in a group chat presents the group welcome / help message."""
    from bot.handlers import user_handlers

    state = bot_test_env["state"]
    await state.set_state(UserQueryState.waiting_for_resolution)

    group_chat = MagicMock(spec=Chat, id=-100777, type="supergroup")
    message = MagicMock(spec=Message, chat=group_chat, from_user=bot_test_env["user"], text="/start")
    message.answer = AsyncMock()
    client = bot_test_env["client"]
    client.is_whitelisted.return_value = False

    monkeypatch.setattr(user_handlers, "is_bot_admin", AsyncMock(return_value=False))

    await handle_start(message, state, bot=bot_test_env["bot"], backend_client=client)

    assert await state.get_state() is None
    message.answer.assert_called_once()
    group_text = message.answer.call_args[0][0]
    assert "Bienvenue sur le Bot du Groupe" in group_text
    assert "/help" in group_text
    assert "/list" in group_text
    assert "/ask" in group_text
    assert "/mute" not in group_text


@pytest.mark.asyncio
async def test_bot_handlers_help_command_sends_help_text(bot_test_env):
    """
    1. FONCTIONNEL:
    /help affiche l'aide utilisateur.
    """
    message = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"])
    message.answer = AsyncMock()
    client = bot_test_env["client"]
    client.is_whitelisted.return_value = False

    await handle_help(message, bot_test_env["bot"], backend_client=client)
    message.answer.assert_called_once()
    assert "Aide" in message.answer.call_args[0][0]
    assert "/list" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_bot_handlers_list_command_alias(bot_test_env):
    """The /list command calls handle_help and returns the command list."""
    message = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"], text="/list")
    message.answer = AsyncMock()
    client = bot_test_env["client"]
    client.is_whitelisted.return_value = False

    await handle_help(message, bot_test_env["bot"], backend_client=client)
    message.answer.assert_called_once()
    assert "/list" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_bot_handlers_help_command_lists_setup_commands_for_whitelisted_admin(bot_test_env, monkeypatch):
    """A whitelisted (non-owner) admin sees the setup commands but not the owner-only /whitelist one."""
    monkeypatch.setattr(settings, "BOT_OWNER_TELEGRAM_ID", 999999)
    message = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"])
    message.answer = AsyncMock()
    client = bot_test_env["client"]
    client.is_whitelisted.return_value = True

    await handle_help(message, bot_test_env["bot"], backend_client=client)
    help_text = message.answer.call_args[0][0]
    assert "/setup_community" in help_text
    assert "/whitelist" not in help_text


@pytest.mark.asyncio
async def test_bot_handlers_help_command_lists_moderation_for_bot_admin_in_community_group(
    bot_test_env, monkeypatch
):
    """A bot admin in the community group sees the moderation commands."""
    from bot.handlers import user_handlers

    group_chat = MagicMock(spec=Chat, id=-100777, type="supergroup")
    message = MagicMock(spec=Message, chat=group_chat, from_user=bot_test_env["user"])
    message.answer = AsyncMock()
    client = bot_test_env["client"]
    client.is_whitelisted.return_value = False

    monkeypatch.setattr(user_handlers, "is_community_group_chat", AsyncMock(return_value=True))
    monkeypatch.setattr(user_handlers, "is_bot_admin", AsyncMock(return_value=True))

    await handle_help(message, bot_test_env["bot"], backend_client=client)
    help_text = message.answer.call_args[0][0]
    assert "/mute" in help_text
    assert "/ask" in help_text


@pytest.mark.asyncio
async def test_bot_handlers_help_command_in_group_for_standard_member_does_not_list_admin_or_setup(
    bot_test_env, monkeypatch
):
    """A standard (non-admin) member in a group sees member commands (/ask, /help, /list, crypto) but no moderation or setup."""
    from bot.handlers import user_handlers

    group_chat = MagicMock(spec=Chat, id=-100777, type="supergroup")
    message = MagicMock(spec=Message, chat=group_chat, from_user=bot_test_env["user"])
    message.answer = AsyncMock()
    client = bot_test_env["client"]
    client.is_whitelisted.return_value = False

    monkeypatch.setattr(user_handlers, "is_bot_admin", AsyncMock(return_value=False))

    await handle_help(message, bot_test_env["bot"], backend_client=client)
    help_text = message.answer.call_args[0][0]
    assert "/ask" in help_text
    assert "/help" in help_text
    assert "/list" in help_text
    assert "/mute" not in help_text
    assert "/ban" not in help_text
    assert "/kick" not in help_text
    assert "/warn" not in help_text
    assert "/purge" not in help_text
    assert "/setup_community" not in help_text
    assert "/whitelist" not in help_text


@pytest.mark.asyncio
async def test_bot_handlers_help_command_for_owner_in_private_chat(bot_test_env, monkeypatch):
    """The bot owner in private chat sees /whitelist and /language."""
    owner_id = bot_test_env["user"].id
    monkeypatch.setattr(settings, "BOT_OWNER_TELEGRAM_ID", owner_id)
    message = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"])
    message.answer = AsyncMock()
    client = bot_test_env["client"]
    client.is_whitelisted.return_value = True

    await handle_help(message, bot_test_env["bot"], backend_client=client)
    help_text = message.answer.call_args[0][0]
    assert "/whitelist" in help_text
    assert "/language" in help_text
    assert "/start" in help_text


@pytest.mark.asyncio
async def test_bot_handlers_help_in_private_chat_for_standard_member_excludes_privileged_commands(bot_test_env, monkeypatch):
    """Standard member in private chat sees general commands but NEVER setup, moderation, or owner commands."""
    monkeypatch.setattr(settings, "BOT_OWNER_TELEGRAM_ID", 999999)
    message = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"])
    message.answer = AsyncMock()
    client = bot_test_env["client"]
    client.is_whitelisted.return_value = False

    await handle_help(message, bot_test_env["bot"], backend_client=client)
    help_text = message.answer.call_args[0][0]

    # Authorized commands
    assert "/start" in help_text
    assert "/help" in help_text
    assert "/list" in help_text

    # Forbidden commands
    assert "/whitelist" not in help_text
    assert "/language" not in help_text
    assert "/setup_community" not in help_text
    assert "/mute" not in help_text
    assert "/ban" not in help_text
    assert "/kick" not in help_text
    assert "/warn" not in help_text
    assert "/purge" not in help_text
    assert "/ask" not in help_text


@pytest.mark.asyncio
async def test_bot_handlers_list_in_group_for_standard_member(bot_test_env, monkeypatch):
    """The /list command in a group chat for standard member shows only member commands."""
    from bot.handlers import user_handlers

    group_chat = MagicMock(spec=Chat, id=-100777, type="supergroup")
    message = MagicMock(spec=Message, chat=group_chat, from_user=bot_test_env["user"], text="/list")
    message.answer = AsyncMock()
    client = bot_test_env["client"]
    client.is_whitelisted.return_value = False

    monkeypatch.setattr(user_handlers, "is_bot_admin", AsyncMock(return_value=False))

    await handle_help(message, bot_test_env["bot"], backend_client=client)
    text = message.answer.call_args[0][0]
    assert "/help" in text
    assert "/list" in text
    assert "/ask" in text
    assert "/mute" not in text
    assert "/ban" not in text
    assert "/setup_community" not in text
    assert "/whitelist" not in text


@pytest.mark.asyncio
async def test_bot_handlers_help_in_group_for_owner_shows_all_commands(bot_test_env, monkeypatch):
    """The bot owner in a group chat sees member, moderation, setup, AND owner commands."""
    from bot.handlers import user_handlers

    owner_id = bot_test_env["user"].id
    monkeypatch.setattr(settings, "BOT_OWNER_TELEGRAM_ID", owner_id)
    group_chat = MagicMock(spec=Chat, id=-100777, type="supergroup")
    message = MagicMock(spec=Message, chat=group_chat, from_user=bot_test_env["user"])
    message.answer = AsyncMock()
    client = bot_test_env["client"]
    client.is_whitelisted.return_value = True

    monkeypatch.setattr(user_handlers, "is_bot_admin", AsyncMock(return_value=True))

    await handle_help(message, bot_test_env["bot"], backend_client=client)
    help_text = message.answer.call_args[0][0]
    assert "/ask" in help_text
    assert "/mute" in help_text
    assert "/setup_community" in help_text
    assert "/whitelist" in help_text


@pytest.mark.asyncio
async def test_bot_handlers_help_bilingual_english(bot_test_env, monkeypatch):
    """Verify English localization of /help for both DM and group."""
    from bot.handlers import user_handlers

    client = bot_test_env["client"]
    client.get_setting.return_value = "en"
    client.is_whitelisted.return_value = False

    # 1. Private chat
    dm_msg = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"])
    dm_msg.answer = AsyncMock()
    await handle_help(dm_msg, bot_test_env["bot"], backend_client=client)
    dm_text = dm_msg.answer.call_args[0][0]
    assert "General commands" in dm_text
    assert "/start" in dm_text

    # 2. Group chat
    group_chat = MagicMock(spec=Chat, id=-100777, type="supergroup")
    group_msg = MagicMock(spec=Message, chat=group_chat, from_user=bot_test_env["user"])
    group_msg.answer = AsyncMock()
    monkeypatch.setattr(user_handlers, "is_bot_admin", AsyncMock(return_value=False))
    await handle_help(group_msg, bot_test_env["bot"], backend_client=client)
    group_text = group_msg.answer.call_args[0][0]
    assert "Below is a list of commands you can use in this group" in group_text or "Member commands" in group_text
    assert "/ask" in group_text



@pytest.mark.asyncio
async def test_bot_handlers_user_query_happy_path_answers_and_sets_waiting_state(bot_test_env):
    """
    1. FUNCTIONAL - Happy Path:
    The user asks a question, the bot queries the backend, shows the answer
    with the YES/NO keyboard and moves to the waiting_for_resolution state.
    """
    client = bot_test_env["client"]
    state = bot_test_env["state"]

    client.query.return_value = {
        "found": True,
        "confidence": 0.85,
        "answer": "Solution KB automatique.",
        "requires_resolution_confirmation": True,
    }

    msg = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"], text="Comment payer ?")
    msg.answer = AsyncMock()

    await handle_user_query(msg, state, backend_client=client)

    msg.answer.assert_called_once()
    sent_text = msg.answer.call_args[0][0]
    assert "Solution KB automatique" in sent_text
    assert "Votre problème est-il résolu ?" in sent_text

    # Check the FSM state and the saved context
    current_state = await state.get_state()
    assert current_state == UserQueryState.waiting_for_resolution.state
    data = await state.get_data()
    assert data["last_question"] == "Comment payer ?"
    assert data["last_answer"] == "Solution KB automatique."


@pytest.mark.asyncio
async def test_bot_handlers_user_query_exceeds_4000_chars_rejected(bot_test_env):
    """
    1. FUNCTIONAL - Max edge case:
    A user message over 4000 characters is rejected without calling the backend.
    """
    client = bot_test_env["client"]
    state = bot_test_env["state"]

    long_text = "Q" * 4001
    msg = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"], text=long_text)
    msg.answer = AsyncMock()

    await handle_user_query(msg, state, backend_client=client)

    msg.answer.assert_called_once()
    assert "trop longue" in msg.answer.call_args[0][0]
    client.query.assert_not_called()


@pytest.mark.asyncio
async def test_bot_handlers_resolve_yes_clears_state_and_marks_resolved(bot_test_env):
    """
    1. FUNCTIONAL:
    The user clicks YES: the message is updated and the FSM state is cleared.
    """
    state = bot_test_env["state"]
    await state.set_state(UserQueryState.waiting_for_resolution)

    cb_message = MagicMock(spec=Message, text="Message précédent")
    cb_message.edit_text = AsyncMock()

    cb = MagicMock(spec=CallbackQuery, data="resolve:yes:0", message=cb_message, from_user=bot_test_env["user"])
    cb.answer = AsyncMock()

    await handle_resolve_yes(cb, state)

    cb.answer.assert_called_once_with("Merci pour votre retour !")
    cb_message.edit_text.assert_called_once()
    assert "Statut : Problème résolu" in cb_message.edit_text.call_args[0][0]
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_bot_handlers_resolve_no_creates_ticket_and_notifies_support_group(bot_test_env, monkeypatch):
    """
    1. FUNCTIONAL:
    The user clicks NO: a backend ticket is created, the Telegram support group
    is notified and the card is attached.
    """
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", -100555666)

    state = bot_test_env["state"]
    await state.update_data(last_question="Panne fibre", last_answer="Redémarrez box")

    client = bot_test_env["client"]
    client.create_ticket.return_value = {"id": 77, "user_id": 1001, "status": "OPEN"}
    client.attach_support_card = AsyncMock()

    bot = bot_test_env["bot"]
    posted_card = MagicMock(message_id=9900)
    bot.send_message.return_value = posted_card

    cb_message = MagicMock(spec=Message, text="Question initiale")
    cb_message.edit_text = AsyncMock()
    cb = MagicMock(spec=CallbackQuery, data="resolve:no:0", message=cb_message, from_user=bot_test_env["user"])
    cb.answer = AsyncMock()

    await handle_resolve_no(cb, state, bot=bot, backend_client=client)

    # 1. Ticket created
    client.create_ticket.assert_called_once()
    assert client.create_ticket.call_args[1]["question"] == "Panne fibre"

    # 2. User message edited
    cb_message.edit_text.assert_called_once()
    assert "Ticket #77 créé et escaladé" in cb_message.edit_text.call_args[0][0]

    # 3. Message sent to the support group
    bot.send_message.assert_called_once()
    assert bot.send_message.call_args[1]["chat_id"] == -100555666
    assert "NOUVEAU TICKET SUPPORT #77" in bot.send_message.call_args[1]["text"]

    # 4. Attachement message_id
    client.attach_support_card.assert_called_once_with(ticket_id=77, message_id=9900)


@pytest.mark.asyncio
async def test_bot_handlers_resolve_no_missing_state_aborts_quietly(bot_test_env):
    """
    1. FUNCTIONAL & IDEMPOTENCE:
    If the user double-clicks NO or the state is empty, the bot simply answers
    'already taken into account' without creating a second ticket.
    """
    state = bot_test_env["state"]
    client = bot_test_env["client"]

    cb = MagicMock(spec=CallbackQuery, data="resolve:no:0", message=MagicMock(), from_user=bot_test_env["user"])
    cb.answer = AsyncMock()

    await handle_resolve_no(cb, state, bot=bot_test_env["bot"], backend_client=client)

    cb.answer.assert_called_once()
    assert "déjà été prise en compte" in cb.answer.call_args[0][0]
    client.create_ticket.assert_not_called()


@pytest.mark.asyncio
async def test_bot_handlers_support_agent_reply_matched_by_message_id_resolves_ticket(monkeypatch):
    """
    1. FUNCTIONAL:
    The agent replies to the support group card; the ticket is found by message_id
    and the solution is forwarded to the user.
    """
    support_group_id = -100555666
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", support_group_id)

    client = AsyncMock(spec=BackendClient)
    client.get_ticket_by_support_message.return_value = {"id": 15, "user_id": 2002, "status": "OPEN"}
    client.resolve_ticket.return_value = {"id": 15, "is_newly_resolved": True, "status": "RESOLVED"}

    bot = AsyncMock()

    group_chat = MagicMock(spec=Chat, id=support_group_id, type="supergroup")
    agent_user = MagicMock(spec=User, id=999, username="agent_tom", first_name="Tom")
    card_msg = MagicMock(spec=Message, message_id=5544)

    reply_msg = MagicMock(
        spec=Message,
        chat=group_chat,
        from_user=agent_user,
        reply_to_message=card_msg,
        text="Voici la solution technique apportée.",
    )
    reply_msg.reply = AsyncMock()

    await handle_support_agent_reply(reply_msg, bot=bot, backend_client=client)

    # 1. Lookup par message id
    client.get_ticket_by_support_message.assert_called_once_with(5544)

    # 2. Backend ticket resolution
    client.resolve_ticket.assert_called_once()

    # 3. Notification forwarded to the user
    bot.send_message.assert_called_once()
    assert bot.send_message.call_args[1]["chat_id"] == 2002
    assert "Voici la solution technique" in bot.send_message.call_args[1]["text"]

    # 4. Confirmation in the support group
    reply_msg.reply.assert_called_once()
    assert "Ticket #15 résolu" in reply_msg.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_bot_handlers_support_agent_reply_matched_by_card_text_fallback_resolves(monkeypatch):
    """
    1. FUNCTIONAL - Text fallback:
    If the ticket is not found by message_id, it is extracted from the card text:
    'NOUVEAU TICKET SUPPORT #25' and 'ID: 3003'.
    """
    support_group_id = -100555666
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", support_group_id)

    client = AsyncMock(spec=BackendClient)
    client.get_ticket_by_support_message.return_value = None  # Lookup by id fails
    client.resolve_ticket.return_value = {"id": 25, "is_newly_resolved": True}

    bot = AsyncMock()
    bot.id = 42

    group_chat = MagicMock(spec=Chat, id=support_group_id, type="supergroup")
    agent_user = MagicMock(spec=User, id=999, username="agent_tom")
    card_text = "🚨 NOUVEAU TICKET SUPPORT #25\nUtilisateur : @toto (ID: 3003)\nQuestion..."
    card_msg = MagicMock(spec=Message, message_id=123, text=card_text, from_user=MagicMock(spec=User, id=bot.id))

    reply_msg = MagicMock(
        spec=Message,
        chat=group_chat,
        from_user=agent_user,
        reply_to_message=card_msg,
        text="Solution fallback.",
    )
    reply_msg.reply = AsyncMock()

    await handle_support_agent_reply(reply_msg, bot=bot, backend_client=client)

    client.resolve_ticket.assert_called_once()
    assert client.resolve_ticket.call_args[1]["ticket_id"] == 25
    bot.send_message.assert_called_once()
    assert bot.send_message.call_args[1]["chat_id"] == 3003


@pytest.mark.asyncio
async def test_bot_handlers_support_agent_reply_already_resolved_notifies_agent(monkeypatch):
    """
    1. FUNCTIONAL:
    If an agent replies to an already resolved ticket, an informational message is shown
    to them and the user is not spammed a second time.
    """
    support_group_id = -100555666
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", support_group_id)

    client = AsyncMock(spec=BackendClient)
    client.get_ticket_by_support_message.return_value = {"id": 10, "user_id": 100, "status": "RESOLVED"}
    client.resolve_ticket.return_value = {
        "id": 10,
        "is_newly_resolved": False,
        "resolved_by": "autre_agent",
    }

    bot = AsyncMock()
    reply_msg = MagicMock(
        spec=Message,
        chat=MagicMock(spec=Chat, id=support_group_id),
        from_user=MagicMock(spec=User, id=1, username="agent1", first_name="Agent", last_name=None),
        reply_to_message=MagicMock(message_id=10),
        text="Solution tardive",
    )
    reply_msg.reply = AsyncMock()

    await handle_support_agent_reply(reply_msg, bot=bot, backend_client=client)

    reply_msg.reply.assert_called_once()
    assert "déjà résolu" in reply_msg.reply.call_args[0][0]
    bot.send_message.assert_not_called()


# ==============================================================================
# 2. SECURITY
# ==============================================================================


@pytest.mark.asyncio
async def test_bot_handlers_agent_reply_from_unauthorized_chat_ignored(monkeypatch):
    """
    2. SECURITY - Chat ID access control:
    A reply written from a private chat or an unconfigured group
    is simply ignored, so nobody can resolve a ticket fraudulently.
    """
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", -100555666)

    client = AsyncMock(spec=BackendClient)
    unauthorized_chat = MagicMock(spec=Chat, id=-999999999)  # Mauvais ID de chat

    reply_msg = MagicMock(
        spec=Message,
        chat=unauthorized_chat,
        reply_to_message=MagicMock(message_id=1),
        text="Tentative de résolution pirate",
    )

    await handle_support_agent_reply(reply_msg, bot=AsyncMock(), backend_client=client)
    client.resolve_ticket.assert_not_called()


@pytest.mark.asyncio
async def test_bot_handlers_agent_reply_from_non_admin_group_member_ignored(monkeypatch):
    """
    2. SECURITY - Admin role access control:
    Being in the right support group is not enough: a plain member
    (non-admin) must never be able to resolve a ticket or speak for
    the support team.
    """
    support_group_id = -100555666
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", support_group_id)
    monkeypatch.setattr(
        "bot.handlers.support_handlers.is_bot_admin",
        AsyncMock(return_value=False),
    )

    client = AsyncMock(spec=BackendClient)
    client.get_ticket_by_support_message.return_value = {"id": 15, "user_id": 2002}

    bot = AsyncMock()
    group_chat = MagicMock(spec=Chat, id=support_group_id, type="supergroup")
    non_admin_user = MagicMock(spec=User, id=321, username="not_an_agent")
    card_msg = MagicMock(spec=Message, message_id=5544)

    reply_msg = MagicMock(
        spec=Message,
        chat=group_chat,
        from_user=non_admin_user,
        reply_to_message=card_msg,
        text="Envoyez vos clés privées à ce lien",
    )
    reply_msg.reply = AsyncMock()

    await handle_support_agent_reply(reply_msg, bot=bot, backend_client=client)

    client.resolve_ticket.assert_not_called()
    bot.send_message.assert_not_called()
    reply_msg.reply.assert_not_called()


# ==============================================================================
# 3. ROBUSTESSE
# ==============================================================================


@pytest.mark.asyncio
async def test_bot_handlers_backend_error_on_query_answers_user_friendly_error(bot_test_env):
    """
    3. ROBUSTNESS - Backend API outage:
    If the backend API is unavailable during the user's query,
    a polite error message is shown without crashing the bot.
    """
    client = bot_test_env["client"]
    client.query.side_effect = ConnectionError("Backend down")

    msg = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"], text="Ma question")
    msg.answer = AsyncMock()

    await handle_user_query(msg, bot_test_env["state"], backend_client=client)

    msg.answer.assert_called_once()
    assert "Une erreur est survenue" in msg.answer.call_args[0][0]


def test_get_webapp_keyboard_group_vs_private():
    """Groups receive a standard url button, while private chats receive a web_app button."""
    from bot.keyboards import get_webapp_keyboard

    # Private chat
    kb_private = get_webapp_keyboard("https://example.com/app", is_group=False)
    btn_private = kb_private.inline_keyboard[0][0]
    assert btn_private.web_app is not None
    assert btn_private.web_app.url == "https://example.com/app"
    assert btn_private.url is None

    # Group chat
    kb_group = get_webapp_keyboard("https://example.com/app", is_group=True)
    btn_group = kb_group.inline_keyboard[0][0]
    assert btn_group.web_app is None
    assert btn_group.url == "https://example.com/app"


@pytest.mark.asyncio
async def test_handle_help_in_group_never_attaches_webapp_or_links(monkeypatch, bot_test_env):
    """In group chats, handle_help never attaches webapp keyboard or links."""
    monkeypatch.setattr(settings, "TELEGRAM_WEBAPP_URL", "https://app.example.com")
    group_chat = MagicMock(spec=Chat, id=-100777, type="supergroup")
    msg = MagicMock(spec=Message, chat=group_chat, from_user=bot_test_env["user"], text="/help")
    msg.answer = AsyncMock()

    client = bot_test_env["client"]
    client.is_whitelisted.return_value = False

    await handle_help(msg, bot_test_env["bot"], backend_client=client)

    msg.answer.assert_called_once()
    markup = msg.answer.call_args.kwargs.get("reply_markup")
    assert markup is None
    answer_text = msg.answer.call_args[0][0]
    assert "/webapp" not in answer_text
    assert "https://app.example.com" not in answer_text


@pytest.mark.asyncio
async def test_handle_webapp_in_group_sends_redirect_message_without_keyboard(monkeypatch):
    """In group chats, /webapp sends a redirect message without any keyboard or webapp link."""
    from bot.handlers.user_handlers import handle_webapp

    monkeypatch.setattr(settings, "TELEGRAM_WEBAPP_URL", "https://app.example.com")
    group_chat = MagicMock(spec=Chat, id=-100777, type="group")
    msg = MagicMock(spec=Message, chat=group_chat, text="/webapp")
    msg.answer = AsyncMock()

    await handle_webapp(msg)

    msg.answer.assert_called_once()
    markup = msg.answer.call_args.kwargs.get("reply_markup")
    assert markup is None
    text = msg.answer.call_args[0][0]
    assert "message privé" in text or "private message" in text



@pytest.mark.asyncio
async def test_bot_handlers_help_in_group_excludes_setup_for_native_admin_who_is_not_whitelisted(
    bot_test_env, monkeypatch
):
    """
    A native Telegram admin of a group who was never whitelisted and isn't the owner must not see
    /setup_community or /whitelist in /help: is_bot_admin() also grants native group admins (for
    moderation, which setup_handlers.py does NOT: it only accepts is_authorized (owner/whitelist).
    """
    from bot.handlers import user_handlers

    monkeypatch.setattr(settings, "BOT_OWNER_TELEGRAM_ID", 999999999)
    group_chat = MagicMock(spec=Chat, id=-100777, type="supergroup")
    message = MagicMock(spec=Message, chat=group_chat, from_user=bot_test_env["user"])
    message.answer = AsyncMock()
    client = bot_test_env["client"]
    client.is_whitelisted.return_value = False

    monkeypatch.setattr(user_handlers, "is_bot_admin", AsyncMock(return_value=True))

    await handle_help(message, bot_test_env["bot"], backend_client=client)
    help_text = message.answer.call_args[0][0]

    assert "/mute" in help_text, "moderation commands should still show for is_bot_admin"
    assert "/setup_community" not in help_text
    assert "/whitelist" not in help_text


# ---------------------------------------------------------------------------
# Ticket reply admin contact notice tests
# ---------------------------------------------------------------------------

def test_agent_handle_helper():
    """Verify _agent_handle formats @username, full name, or Admin_<id>."""
    from bot.handlers.support_handlers import _agent_handle

    u1 = MagicMock(spec=User, id=101, username="agent_sophie", first_name="Sophie", last_name=None)
    assert _agent_handle(u1) == "@agent_sophie"

    u2 = MagicMock(spec=User, id=102, username="@agent_marc", first_name="Marc", last_name=None)
    assert _agent_handle(u2) == "@agent_marc"

    u3 = MagicMock(spec=User, id=103, username="  agent_claire  ", first_name="Claire", last_name=None)
    assert _agent_handle(u3) == "@agent_claire"

    u4 = MagicMock(spec=User, id=104, username=None, first_name="Jean", last_name="Dupont")
    assert _agent_handle(u4) == "Jean Dupont"

    u5 = MagicMock(spec=User, id=105, username="", first_name="Sophie", last_name=None)
    assert _agent_handle(u5) == "Sophie"

    u6 = MagicMock(spec=User, id=106, username="", first_name="", last_name=None)
    assert _agent_handle(u6) == "Admin_106"


@pytest.mark.asyncio
async def test_support_agent_reply_notifies_user_and_group_with_admin_handle(monkeypatch):
    """When an agent resolves a ticket, both user DM and community group include admin contact notice."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 50
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Voici la solution au problème."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "fr"
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 200,
        "user_id": 789,
        "user_handle": "marc789",
        "source_chat_id": -100555666,
        "source_message_id": 333,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 200,
        "user_id": 789,
        "user_handle": "marc789",
        "status": "RESOLVED",
        "is_newly_resolved": True,
        "source_chat_id": -100555666,
        "source_message_id": 333,
    }

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    assert mock_bot.send_message.call_count == 2
    dm_call = mock_bot.send_message.call_args_list[0]
    group_call = mock_bot.send_message.call_args_list[1]

    # 1. User DM checks
    assert dm_call.kwargs["chat_id"] == 789
    dm_text = dm_call.kwargs["text"]
    assert "Si vous n'êtes pas satisfait, vous pouvez contacter directement @agent\\_sophie." in dm_text
    assert "Traité par" not in dm_text
    assert "Handled by" not in dm_text

    # 2. Community group notification checks
    assert group_call.kwargs["chat_id"] == -100555666
    group_text = group_call.kwargs["text"]
    assert "Si vous n'êtes pas satisfait, vous pouvez contacter directement @agent\\_sophie." in group_text
    assert "Traité par" not in group_text
    assert "Handled by" not in group_text


@pytest.mark.asyncio
async def test_support_agent_reply_markdown_fallback_uses_plain_notice(monkeypatch):
    """When sending with Markdown fails, fallback sends plain notification with unescaped handle."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    # Bot fails on markdown for DM, then succeeds in plain text
    mock_bot = AsyncMock()
    mock_bot.id = 42
    mock_bot.send_message.side_effect = [
        Exception("Bad Request: can't parse entities"),
        MagicMock(message_id=101),
    ]

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 50
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Voici la solution."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "fr"
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 200,
        "user_id": 789,
        "user_handle": "marc789",
        "source_chat_id": None,
        "source_message_id": None,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 200,
        "user_id": 789,
        "user_handle": "marc789",
        "status": "RESOLVED",
        "is_newly_resolved": True,
    }

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    assert mock_bot.send_message.call_count == 2
    retry_call = mock_bot.send_message.call_args_list[1]
    assert "Si vous n'êtes pas satisfait, vous pouvez contacter directement @agent_sophie." in retry_call.kwargs["text"]
    assert "Traité par" not in retry_call.kwargs["text"]
    assert "Handled by" not in retry_call.kwargs["text"]
    assert "parse_mode" not in retry_call.kwargs


@pytest.mark.asyncio
async def test_support_agent_reply_admin_without_username_uses_full_name(monkeypatch):
    """When an agent has no Telegram username, their display name is used in the contact notice."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=88, username=None, first_name="Sophie", last_name="Martin")
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 556
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 51
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Solution de Sophie."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "fr"
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 201,
        "user_id": 789,
        "user_handle": "marc789",
        "source_chat_id": -100555666,
        "source_message_id": 334,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 201,
        "user_id": 789,
        "user_handle": "marc789",
        "status": "RESOLVED",
        "is_newly_resolved": True,
        "source_chat_id": -100555666,
        "source_message_id": 334,
    }

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    dm_call = mock_bot.send_message.call_args_list[0]
    group_call = mock_bot.send_message.call_args_list[1]

    assert "Si vous n'êtes pas satisfait, vous pouvez contacter directement Sophie Martin." in dm_call.kwargs["text"]
    assert "Si vous n'êtes pas satisfait, vous pouvez contacter directement Sophie Martin." in group_call.kwargs["text"]


@pytest.mark.asyncio
async def test_support_agent_reply_english_localization(monkeypatch):
    """Verify English localization includes the dissatisfaction notice with admin handle."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 557
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 52
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "English solution."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 202,
        "user_id": 789,
        "user_handle": "marc789",
        "source_chat_id": -100555666,
        "source_message_id": 335,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 202,
        "user_id": 789,
        "user_handle": "marc789",
        "status": "RESOLVED",
        "is_newly_resolved": True,
        "source_chat_id": -100555666,
        "source_message_id": 335,
    }

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    dm_call = mock_bot.send_message.call_args_list[0]
    group_call = mock_bot.send_message.call_args_list[1]

    assert "If you are not satisfied, you can contact @agent\\_sophie directly." in dm_call.kwargs["text"]
    assert "If you are not satisfied, you can contact @agent\\_sophie directly." in group_call.kwargs["text"]
    assert "Handled by" not in dm_call.kwargs["text"]
    assert "Handled by" not in group_call.kwargs["text"]
    assert "Traité par" not in dm_call.kwargs["text"]
    assert "Traité par" not in group_call.kwargs["text"]


@pytest.mark.asyncio
async def test_support_agent_reply_community_group_markdown_fallback_uses_plain_notice(monkeypatch):
    """When sending community group notification with Markdown fails, fallback sends plain notification."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    # DM succeeds, group reply fails on markdown then succeeds on plain text
    mock_bot.send_message.side_effect = [
        MagicMock(message_id=201),  # DM send succeeds
        Exception("Bad Request: can't parse entities"),  # Group markdown fails
        MagicMock(message_id=202),  # Group plain retry succeeds
    ]

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 558
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 53
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Solution pour le groupe."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "fr"
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 203,
        "user_id": 789,
        "user_handle": "marc789",
        "source_chat_id": -100555666,
        "source_message_id": 336,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 203,
        "user_id": 789,
        "user_handle": "marc789",
        "status": "RESOLVED",
        "is_newly_resolved": True,
        "source_chat_id": -100555666,
        "source_message_id": 336,
    }

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    assert mock_bot.send_message.call_count == 3
    # Call 0: DM
    # Call 1: Group (markdown attempt, failed)
    # Call 2: Group (plain text fallback)
    group_fallback_call = mock_bot.send_message.call_args_list[2]
    assert group_fallback_call.kwargs["chat_id"] == -100555666
    assert "parse_mode" not in group_fallback_call.kwargs
    assert "Si vous n'êtes pas satisfait, vous pouvez contacter directement @agent_sophie." in group_fallback_call.kwargs["text"]
    assert "Traité par" not in group_fallback_call.kwargs["text"]
    assert "Handled by" not in group_fallback_call.kwargs["text"]


@pytest.mark.asyncio
async def test_support_agent_reply_admin_with_markdown_characters_escaped_in_notice(monkeypatch):
    """Admin display name containing markdown special characters is escaped in Markdown and unescaped in plain."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=77, username=None, first_name="Super_Admin*", last_name="[Staff]")
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 559
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 54
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Solution avec admin aux caractères spéciaux."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "fr"
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 204,
        "user_id": 789,
        "user_handle": "marc789",
        "source_chat_id": -100555666,
        "source_message_id": 337,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 204,
        "user_id": 789,
        "user_handle": "marc789",
        "status": "RESOLVED",
        "is_newly_resolved": True,
        "source_chat_id": -100555666,
        "source_message_id": 337,
    }

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    dm_call = mock_bot.send_message.call_args_list[0]
    group_call = mock_bot.send_message.call_args_list[1]

    # Markdown escaped handle in message
    assert "Super\\_Admin\\* \\[Staff]" in dm_call.kwargs["text"]
    assert "Super\\_Admin\\* \\[Staff]" in group_call.kwargs["text"]


@pytest.mark.parametrize(
    "raw_username,expected_in_markdown,expected_in_plain",
    [
        ("SAGBO4", "@SAGBO4", "@SAGBO4"),
        ("alice_support", "@alice\\_support", "@alice_support"),
        ("charlie_admin", "@charlie\\_admin", "@charlie_admin"),
    ],
)
@pytest.mark.asyncio
async def test_support_agent_reply_dynamic_admin_username_per_admin(
    raw_username, expected_in_markdown, expected_in_plain, monkeypatch
):
    """Prove that each different admin replying gets their own specific username dynamically inserted."""
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=123, username=raw_username, first_name="Admin", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    mock_bot = AsyncMock()
    mock_bot.id = 42

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 700
    replied_card.from_user = MagicMock(spec=User, id=mock_bot.id)

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 60
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = f"Solution fournie par {raw_username}."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "fr"
    mock_client.get_ticket_by_support_message.return_value = {
        "id": 300,
        "user_id": 999,
        "user_handle": "client999",
        "source_chat_id": -100444555,
        "source_message_id": 888,
    }
    mock_client.resolve_ticket.return_value = {
        "id": 300,
        "user_id": 999,
        "user_handle": "client999",
        "status": "RESOLVED",
        "is_newly_resolved": True,
        "source_chat_id": -100444555,
        "source_message_id": 888,
    }

    await handle_support_agent_reply(agent_message, bot=mock_bot, backend_client=mock_client)

    assert mock_bot.send_message.call_count == 2
    dm_call = mock_bot.send_message.call_args_list[0]
    group_call = mock_bot.send_message.call_args_list[1]

    # 1. Verify User DM contains the admin's specific username
    assert dm_call.kwargs["chat_id"] == 999
    dm_text = dm_call.kwargs["text"]
    assert f"Si vous n'êtes pas satisfait, vous pouvez contacter directement {expected_in_markdown}." in dm_text

    # 2. Verify Community Group Reply contains the admin's specific username
    assert group_call.kwargs["chat_id"] == -100444555
    group_text = group_call.kwargs["text"]
    assert f"Si vous n'êtes pas satisfait, vous pouvez contacter directement {expected_in_markdown}." in group_text



