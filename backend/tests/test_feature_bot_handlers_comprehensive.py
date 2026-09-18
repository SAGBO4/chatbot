import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import User, Chat, Message, CallbackQuery, Voice
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from backend.config import settings
from bot.handlers.user_handlers import (
    handle_start,
    handle_help,
    handle_user_query,
    handle_resolve_yes,
    handle_resolve_no,
    UserQueryState,
)
from bot.handlers.support_handlers import handle_support_agent_reply
from bot.api_client import BackendClient


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
    1. FONCTIONNEL:
    /start réinitialise l'état FSM et envoie le message d'accueil.
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
async def test_bot_handlers_help_command_sends_help_text(bot_test_env):
    """
    1. FONCTIONNEL:
    /help affiche l'aide utilisateur.
    """
    message = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"])
    message.answer = AsyncMock()

    await handle_help(message)
    message.answer.assert_called_once()
    assert "Aide" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_bot_handlers_user_query_happy_path_answers_and_sets_waiting_state(bot_test_env):
    """
    1. FONCTIONNEL - Happy Path:
    L'utilisateur pose une question, le bot consulte le backend,
    affiche la réponse avec le clavier OUI/NON et passe à l'état waiting_for_resolution.
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

    # Vérification état FSM et contexte sauvegardé
    current_state = await state.get_state()
    assert current_state == UserQueryState.waiting_for_resolution.state
    data = await state.get_data()
    assert data["last_question"] == "Comment payer ?"
    assert data["last_answer"] == "Solution KB automatique."


@pytest.mark.asyncio
async def test_bot_handlers_user_query_exceeds_4000_chars_rejected(bot_test_env):
    """
    1. FONCTIONNEL - Cas limite Max:
    Message utilisateur > 4000 caractères rejeté sans appeler le backend.
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
    1. FONCTIONNEL:
    L'utilisateur clique sur OUI: le message est mis à jour et l'état FSM est nettoyé.
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
    1. FONCTIONNEL:
    L'utilisateur clique sur NON: création d'un ticket backend,
    notification au groupe support Telegram et attachement de la carte.
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

    # 1. Ticket créé
    client.create_ticket.assert_called_once()
    assert client.create_ticket.call_args[1]["question"] == "Panne fibre"

    # 2. Message utilisateur édité
    cb_message.edit_text.assert_called_once()
    assert "Ticket #77 créé et escaladé" in cb_message.edit_text.call_args[0][0]

    # 3. Message envoyé au groupe support
    bot.send_message.assert_called_once()
    assert bot.send_message.call_args[1]["chat_id"] == -100555666
    assert "NOUVEAU TICKET SUPPORT #77" in bot.send_message.call_args[1]["text"]

    # 4. Attachement message_id
    client.attach_support_card.assert_called_once_with(ticket_id=77, message_id=9900)


@pytest.mark.asyncio
async def test_bot_handlers_resolve_no_missing_state_aborts_quietly(bot_test_env):
    """
    1. FONCTIONNEL & IDEMPOTENCE:
    Si l'utilisateur double-clique sur NON ou que l'état est vide,
    le bot répond simplement 'déjà prise en compte' sans créer de 2e ticket.
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
    1. FONCTIONNEL:
    L'agent répond à la carte du groupe support; le ticket est retrouvé par message_id
    et la solution est transmise à l'utilisateur.
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

    # 2. Résolution ticket backend
    client.resolve_ticket.assert_called_once()

    # 3. Notification transmise à l'utilisateur
    bot.send_message.assert_called_once()
    assert bot.send_message.call_args[1]["chat_id"] == 2002
    assert "Voici la solution technique" in bot.send_message.call_args[1]["text"]

    # 4. Confirmation dans le groupe support
    reply_msg.reply.assert_called_once()
    assert "Ticket #15 résolu" in reply_msg.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_bot_handlers_support_agent_reply_matched_by_card_text_fallback_resolves(monkeypatch):
    """
    1. FONCTIONNEL - Fallback texte:
    Si le ticket n'est pas trouvé par message_id, il est extrait du texte de la carte:
    'NOUVEAU TICKET SUPPORT #25' et 'ID: 3003'.
    """
    support_group_id = -100555666
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", support_group_id)

    client = AsyncMock(spec=BackendClient)
    client.get_ticket_by_support_message.return_value = None  # Lookup par id échoue
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
    1. FONCTIONNEL:
    Si un agent répond à un ticket déjà résolu, un message d'information lui est affiché
    et l'utilisateur n'est pas spammé une seconde fois.
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
# 2. SÉCURITÉ
# ==============================================================================


@pytest.mark.asyncio
async def test_bot_handlers_agent_reply_from_unauthorized_chat_ignored(monkeypatch):
    """
    2. SÉCURITÉ - Contrôle d'accès Chat ID:
    Une réponse formulée depuis un chat privé ou un groupe non configuré
    est purement ignorée pour empêcher toute résolution frauduleuse.
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
    2. SÉCURITÉ - Contrôle d'accès rôle admin:
    Être présent dans le bon groupe support ne suffit pas: un simple membre
    (non admin) ne doit jamais pouvoir résoudre un ticket ni parler au nom
    de l'équipe support.
    """
    support_group_id = -100555666
    monkeypatch.setattr(settings, "TELEGRAM_SUPPORT_GROUP_ID", support_group_id)
    monkeypatch.setattr(
        "bot.handlers.support_handlers.is_group_admin",
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
    3. ROBUSTESSE - Panne Backend API:
    Si le backend API est indisponible pendant la requête utilisateur,
    un message d'erreur poli est affiché sans crasher le bot.
    """
    client = bot_test_env["client"]
    client.query.side_effect = ConnectionError("Backend down")

    msg = MagicMock(spec=Message, chat=bot_test_env["chat"], from_user=bot_test_env["user"], text="Ma question")
    msg.answer = AsyncMock()

    await handle_user_query(msg, bot_test_env["state"], backend_client=client)

    msg.answer.assert_called_once()
    assert "Une erreur est survenue" in msg.answer.call_args[0][0]
