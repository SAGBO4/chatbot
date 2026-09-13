import pytest
from unittest.mock import AsyncMock, MagicMock
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
    monkeypatch.setattr("backend.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

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
    monkeypatch.setattr("backend.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

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
async def test_support_agent_reply_falls_back_to_text_when_id_lookup_misses(monkeypatch):
    """When the id-based lookup finds nothing (e.g. a ticket created before this
    mechanism existed), the previous text-parsing behavior still resolves it."""
    monkeypatch.setattr("backend.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    agent_user = MagicMock(spec=User, id=99, username="agent_sophie", first_name="Sophie", last_name=None)
    group_chat = MagicMock(spec=Chat, id=-100999888, type="supergroup")

    replied_card = MagicMock(spec=Message)
    replied_card.message_id = 555
    replied_card.text = "🚨 NOUVEAU TICKET SUPPORT #101\n👤 Utilisateur : @marc789 (ID: 789)\n❓ Question : Erreur sync"

    agent_message = MagicMock(spec=Message)
    agent_message.message_id = 51
    agent_message.chat = group_chat
    agent_message.from_user = agent_user
    agent_message.text = "Veuillez redémarrer le daemon de synchronisation via systemctl restart sync-daemon."
    agent_message.reply_to_message = replied_card
    agent_message.reply = AsyncMock()

    mock_bot = AsyncMock()
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
async def test_support_agent_reply_no_match_replies_with_explicit_notice(monkeypatch):
    """When neither the id-based lookup nor the text fallback identify a
    ticket, the bot must not resolve anything and must say so explicitly."""
    monkeypatch.setattr("backend.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

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


@pytest.mark.asyncio
async def test_support_agent_reply_ignored_from_private_chat(monkeypatch):
    monkeypatch.setattr("backend.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

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
    monkeypatch.setattr("backend.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

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
    monkeypatch.setattr("backend.config.settings.TELEGRAM_SUPPORT_GROUP_ID", 0)

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
