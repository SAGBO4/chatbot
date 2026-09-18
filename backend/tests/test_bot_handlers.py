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
        "bot.handlers.support_handlers.is_group_admin",
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



