import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from aiogram.types import User, Chat, Message, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.fsm.context import FSMContext

from app.main import app
from app.database import get_db, init_db
from app.config import settings
from app.models import Ticket, TicketStatus
from sqlalchemy import select
from bot.api_client import BackendClient
from bot.handlers.user_handlers import (
    handle_user_query,
    handle_resolve_no,
    handle_resolve_yes,
)
from bot.handlers.support_handlers import handle_support_agent_reply

TEST_API_KEY = "test-api-key"


@pytest_asyncio.fixture
async def e2e_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", TEST_API_KEY)
    monkeypatch.setattr(settings, "AI_ENABLED", False)

    # 1. Setup in-memory / temporary database
    db_file = tmp_path / "e2e_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    await init_db(db_engine=engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # 2. Client connecting to in-memory ASGI app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", headers={"X-API-Key": TEST_API_KEY}
    ) as client:
        backend_client = BackendClient(base_url="http://testserver")
        # Patch BackendClient to route via ASGI transport
        backend_client.query = lambda query, user_id, user_handle=None: client.post(
            "/api/query", json={"query": query, "user_id": user_id, "user_handle": user_handle}
        ).then(lambda r: r.json()) if False else None

        # Direct async wrapping for BackendClient with ASGI test client
        async def mock_query(query: str, user_id: int, user_handle: str = None):
            r = await client.post("/api/query", json={"query": query, "user_id": user_id, "user_handle": user_handle})
            return r.json()

        async def mock_create_ticket(user_id: int, user_handle: str, question: str, automated_answer: str = None):
            r = await client.post(
                "/api/tickets",
                json={"user_id": user_id, "user_handle": user_handle, "question": question, "automated_answer": automated_answer},
            )
            return r.json()

        async def mock_resolve_ticket(ticket_id: int, solution: str, resolved_by: str = None, add_to_knowledge_base: bool = True):
            r = await client.post(
                f"/api/tickets/{ticket_id}/resolve",
                json={"solution": solution, "resolved_by": resolved_by, "add_to_knowledge_base": add_to_knowledge_base},
            )
            return r.json()

        async def mock_attach_support_card(ticket_id: int, message_id: int):
            r = await client.post(
                f"/api/tickets/{ticket_id}/support-card",
                json={"message_id": message_id},
            )
            return r.json()

        async def mock_get_ticket_by_support_message(message_id: int):
            r = await client.get(f"/api/tickets/by-support-message/{message_id}")
            if r.status_code == 404:
                return None
            return r.json()

        backend_client.attach_support_card = mock_attach_support_card
        backend_client.get_ticket_by_support_message = mock_get_ticket_by_support_message
        backend_client.query = mock_query
        backend_client.create_ticket = mock_create_ticket
        backend_client.resolve_ticket = mock_resolve_ticket

        yield backend_client, session_maker

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_full_support_lifecycle_loop(e2e_environment, monkeypatch):
    """
    Tests the complete workflow from the user's diagram:
    Telegram User -> Bot -> Backend -> KB (No match)
      -> Resolution Check (NON)
      -> Ticket Created
      -> Team Support Group Notified
      -> Agent Reply (New Solution)
      -> User Notified
      -> Knowledge Base Auto-Updated
      -> Repeat Question (Match Found!)
      -> Resolution Check (OUI)
      -> FIN
    """
    backend_client, session_maker = e2e_environment
    storage = MemoryStorage()
    support_group_id = -100555666777
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", support_group_id)

    user = MagicMock(spec=User, id=1001, username="david_user", first_name="David")
    user_chat = MagicMock(spec=Chat, id=1001, type="private")
    user_state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=1001, user_id=1001))
    mock_bot = AsyncMock()
    # The group card's posted message; its id is what links the ticket to the
    # agent's later reply (see harden-support-reply-ticket-lookup).
    posted_card_message_id = 7001
    mock_bot.send_message.return_value = MagicMock(message_id=posted_card_message_id)

    # Step 1: User asks a new, unknown question
    initial_question = "Mon imprimante affiche erreur 404 sur l'écran"
    user_msg_1 = MagicMock(spec=Message, chat=user_chat, from_user=user, text=initial_question)
    user_msg_1.answer = AsyncMock()

    await handle_user_query(user_msg_1, user_state, backend_client=backend_client)

    # Bot responds with fallback and asks if problem is resolved
    user_msg_1.answer.assert_called_once()
    initial_answer = user_msg_1.answer.call_args[0][0]
    assert "Je n'ai pas trouvé de réponse directe" in initial_answer
    assert "Votre problème est-il résolu ?" in initial_answer

    # Step 2: User clicks "NON" (problème non résolu -> TICKET)
    cb_msg_1 = MagicMock(spec=Message, text=initial_answer)
    cb_msg_1.edit_text = AsyncMock()
    callback_no = MagicMock(
        spec=CallbackQuery,
        id="cb_no_step2",
        from_user=user,
        data="resolve:no:0",
        message=cb_msg_1,
    )
    callback_no.answer = AsyncMock()

    await handle_resolve_no(callback_no, user_state, bot=mock_bot, backend_client=backend_client)

    # Verifies user informed of ticket creation
    assert "Ticket #1 créé et escaladé" in cb_msg_1.edit_text.call_args[0][0]

    # Verifies card posted to Team Support Telegram Group
    mock_bot.send_message.assert_called_once()
    group_card = mock_bot.send_message.call_args.kwargs["text"]
    assert "NOUVEAU TICKET SUPPORT #1" in group_card
    assert "David" in group_card or "david_user" in group_card or "david\\_user" in group_card
    assert initial_question in group_card

    # Verifies the card's Telegram message id was persisted against the ticket
    async with session_maker() as verify_session:
        persisted_ticket = (
            await verify_session.execute(select(Ticket).where(Ticket.id == 1))
        ).scalars().first()
        assert persisted_ticket.support_group_message_id == posted_card_message_id

    # Step 3: Support Agent replies in the Support Group with a new solution
    agent_user = MagicMock(spec=User, id=2002, username="support_hero", first_name="Hero")
    group_chat = MagicMock(spec=Chat, id=support_group_id, type="supergroup")

    card_in_group = MagicMock(
        spec=Message, chat=group_chat, text=group_card, message_id=posted_card_message_id
    )
    agent_solution = "Éteignez l'imprimante 30 secondes puis rebranchez le câble réseau."

    agent_reply_msg = MagicMock(
        spec=Message,
        chat=group_chat,
        from_user=agent_user,
        text=agent_solution,
        reply_to_message=card_in_group,
    )
    agent_reply_msg.reply = AsyncMock()

    # Clear mock_bot call history before agent reply
    mock_bot.send_message.reset_mock()

    await handle_support_agent_reply(agent_reply_msg, bot=mock_bot, backend_client=backend_client)

    # Solution forwarded to user
    mock_bot.send_message.assert_called_once()
    user_direct_msg = mock_bot.send_message.call_args.kwargs["text"]
    assert mock_bot.send_message.call_args.kwargs["chat_id"] == 1001
    assert agent_solution in user_direct_msg

    # Support group confirmation
    agent_reply_msg.reply.assert_called_once()
    assert "Ticket #1 résolu" in agent_reply_msg.reply.call_args[0][0]
    assert "base de connaissances" in agent_reply_msg.reply.call_args[0][0]

    # Step 4: A second user asks the same question (Repeat Query)
    user2 = MagicMock(spec=User, id=3003, username="emma", first_name="Emma")
    user2_chat = MagicMock(spec=Chat, id=3003, type="private")
    user2_state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=3003, user_id=3003))

    user_msg_2 = MagicMock(spec=Message, chat=user2_chat, from_user=user2, text="J'ai une erreur 404 sur mon imprimante")
    user_msg_2.answer = AsyncMock()

    await handle_user_query(user_msg_2, user2_state, backend_client=backend_client)

    # Bot now answers automatically from the Knowledge Base with the support solution!
    user_msg_2.answer.assert_called_once()
    auto_answer_2 = user_msg_2.answer.call_args[0][0]
    assert agent_solution in auto_answer_2
    assert "Votre problème est-il résolu ?" in auto_answer_2

    # Step 5: User 2 clicks "OUI" (Problème résolu -> FIN)
    cb_msg_2 = MagicMock(spec=Message, text=auto_answer_2)
    cb_msg_2.edit_text = AsyncMock()
    callback_yes = MagicMock(
        spec=CallbackQuery,
        id="cb_yes_step5",
        from_user=user2,
        data="resolve:yes:0",
        message=cb_msg_2,
    )
    callback_yes.answer = AsyncMock()

    await handle_resolve_yes(callback_yes, user2_state)

    # Interaction closed cleanly
    cb_msg_2.edit_text.assert_called_once()
    assert "Problème résolu" in cb_msg_2.edit_text.call_args[0][0]
