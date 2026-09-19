import logging
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from aiogram import Bot
from aiogram.types import Update, Message, Chat, User

from bot.main import create_dispatcher

COMMUNITY_GROUP_ID = -100555111
OTHER_GROUP_ID = -100999999
SUPPORT_GROUP_ID = -100777333


async def _fake_get_community_group_id(backend_client=None):
    return COMMUNITY_GROUP_ID


@pytest.fixture(autouse=True)
def configure_community_group(monkeypatch):
    monkeypatch.setattr("bot.group_scope.get_community_group_id", _fake_get_community_group_id)


def make_test_bot() -> Bot:
    bot = Bot(token="123456789:AAFakeTestTokenForDispatcherRoutingTest")
    bot.restrict_chat_member = AsyncMock(return_value=True)
    bot.ban_chat_member = AsyncMock(return_value=True)
    bot.unban_chat_member = AsyncMock(return_value=True)
    bot.get_chat_member = AsyncMock(return_value=MagicMock(status="administrator"))
    # Message.reply()/answer() shortcuts call Bot.__call__ -> self.session(...)
    # directly (bypassing bot.send_message), so the underlying session itself
    # must be faked to avoid a real network call.
    bot.session = AsyncMock(return_value=MagicMock(message_id=1))
    return bot


def make_command_update(update_id, chat_id, user_id, command_text, chat_type="supergroup") -> Update:
    chat = Chat(id=chat_id, type=chat_type)
    user = User(id=user_id, is_bot=False, first_name="Admin", username="admin_x")
    message = Message(
        message_id=update_id,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=user,
        text=command_text,
    )
    return Update(update_id=update_id, message=message)


def make_reply_update(update_id, chat_id, user_id, text, replied_user_id, replied_is_bot=False, chat_type="supergroup") -> Update:
    """An update where `user_id` sends `text` as a reply to a message written by `replied_user_id`."""
    chat = Chat(id=chat_id, type=chat_type)
    sender = User(id=user_id, is_bot=False, first_name="Sender", username=f"user_{user_id}")
    replied_author = User(id=replied_user_id, is_bot=replied_is_bot, first_name="Replied")
    replied = Message(
        message_id=update_id - 1,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=replied_author,
        text="the message being replied to",
    )
    message = Message(
        message_id=update_id,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=sender,
        text=text,
        reply_to_message=replied,
    )
    return Update(update_id=update_id, message=message)


@pytest.fixture(scope="module")
def dispatcher():
    # create_dispatcher() attaches module-level singleton routers to the
    # Dispatcher it builds; a router can only ever have one parent, so every
    # case in this module must share a single Dispatcher/Bot instance
    # (multiple real Telegram updates through one running bot process, which
    # is exactly what this test simulates) rather than each building its own.
    mock_client = AsyncMock()
    mock_client.create_warning.return_value = {"id": 1}
    mock_client.list_warnings.return_value = {"count": 1, "warnings": []}
    dp = create_dispatcher(backend_client=mock_client)
    bot = make_test_bot()
    return dp, bot, mock_client


@pytest.fixture(autouse=True)
def reset_mocks(dispatcher):
    _, bot, mock_client = dispatcher
    mock_client.reset_mock()
    bot.restrict_chat_member.reset_mock()
    bot.ban_chat_member.reset_mock()
    bot.unban_chat_member.reset_mock()
    yield


@pytest.mark.parametrize(
    "command_text,expected_bot_method",
    [
        ("/mute 991", "restrict_chat_member"),
        ("/unmute 992", "restrict_chat_member"),
        ("/ban 993", "ban_chat_member"),
        ("/kick 994", "ban_chat_member"),
    ],
)
@pytest.mark.asyncio
async def test_moderation_commands_route_inside_community_group(dispatcher, command_text, expected_bot_method):
    dp, bot, _ = dispatcher
    update = make_command_update(1, COMMUNITY_GROUP_ID, user_id=1, command_text=command_text)

    await dp.feed_update(bot, update)

    getattr(bot, expected_bot_method).assert_called()


@pytest.mark.asyncio
async def test_warn_command_routes_inside_community_group(dispatcher):
    dp, bot, mock_client = dispatcher
    update = make_command_update(2, COMMUNITY_GROUP_ID, user_id=1, command_text="/warn 995 spam")

    await dp.feed_update(bot, update)

    mock_client.create_warning.assert_called_once()


@pytest.mark.parametrize(
    "command_text,user_id",
    [("/mute 999", 801), ("/unmute 999", 802), ("/ban 999", 803), ("/kick 999", 804), ("/warn 999 spam", 805)],
)
@pytest.mark.asyncio
async def test_moderation_commands_do_not_route_outside_community_group(dispatcher, caplog, command_text, user_id):
    # One user id per case: the shared dispatcher throttles per user, and a throttled message would
    # make this test pass without the handler ever deciding anything.
    dp, bot, mock_client = dispatcher
    update = make_command_update(3, OTHER_GROUP_ID, user_id=user_id, command_text=command_text)

    with caplog.at_level(logging.WARNING):
        await dp.feed_update(bot, update)

    assert "Throttling" not in caplog.text
    bot.restrict_chat_member.assert_not_called()
    bot.ban_chat_member.assert_not_called()
    mock_client.create_warning.assert_not_called()


@pytest.mark.parametrize(
    "chat_id,chat_type,user_id",
    [(COMMUNITY_GROUP_ID, "supergroup", 501), (12345, "private", 502)],
)
@pytest.mark.asyncio
async def test_crypto_command_routes_in_private_and_community_chats(dispatcher, chat_id, chat_type, user_id):
    # Distinct user_id per case: the shared dispatcher's ThrottlingMiddleware
    # tracks a real sliding window per user across this whole module's tests.
    dp, bot, mock_client = dispatcher
    mock_client.get_crypto_price.return_value = {
        "symbol": "btc", "price_usd": 1.0, "change_24h_pct": 0.0,
        "market_cap_usd": 1.0, "volume_24h_usd": 1.0,
    }
    update = make_command_update(4, chat_id, user_id=user_id, command_text="/btc", chat_type=chat_type)

    await dp.feed_update(bot, update)

    mock_client.get_crypto_price.assert_called_once_with("btc")


@pytest.mark.asyncio
async def test_authorized_owner_sees_setup_tutorial_when_no_community_group(dispatcher, monkeypatch):
    dp, bot, mock_client = dispatcher
    monkeypatch.setattr("app.config.settings.BOT_OWNER_TELEGRAM_ID", 601)

    async def no_group(backend_client=None):
        return None
    monkeypatch.setattr("bot.handlers.setup_handlers.get_community_group_id", no_group)

    update = make_command_update(5, 601, user_id=601, command_text="/start", chat_type="private")
    await dp.feed_update(bot, update)

    sent_text = bot.session.call_args.args[1].text
    assert "communautaire" in sent_text


@pytest.mark.asyncio
async def test_non_authorized_user_falls_through_to_normal_welcome(dispatcher, monkeypatch):
    dp, bot, mock_client = dispatcher
    monkeypatch.setattr("app.config.settings.BOT_OWNER_TELEGRAM_ID", 601)

    # The setup filter calls is_authorized() without a client, which would open a real
    # BackendClient (and a real connection attempt): decide the answer here instead.
    async def not_authorized(user_id, backend_client=None):
        return False
    monkeypatch.setattr("bot.handlers.setup_handlers.is_authorized", not_authorized)

    async def no_group(backend_client=None):
        return None
    monkeypatch.setattr("bot.handlers.setup_handlers.get_community_group_id", no_group)

    update = make_command_update(6, 602, user_id=602, command_text="/start", chat_type="private")
    await dp.feed_update(bot, update)

    sent_text = bot.session.call_args.args[1].text
    assert "bienvenue" in sent_text.lower()
    assert "communautaire" not in sent_text


@pytest.mark.parametrize(
    "command_text,expected_bot_method,sender_id",
    [
        ("/mute", "restrict_chat_member", 711),
        ("/unmute", "restrict_chat_member", 712),
        ("/ban", "ban_chat_member", 713),
        ("/kick", "ban_chat_member", 714),
    ],
)
@pytest.mark.asyncio
async def test_moderation_command_sent_as_a_reply_targets_the_replied_author(
    dispatcher, command_text, expected_bot_method, sender_id
):
    dp, bot, _ = dispatcher
    update = make_reply_update(20, COMMUNITY_GROUP_ID, user_id=sender_id, text=command_text, replied_user_id=42)

    await dp.feed_update(bot, update)

    method = getattr(bot, expected_bot_method)
    method.assert_called_once()
    assert method.call_args.kwargs["user_id"] == 42


@pytest.mark.asyncio
async def test_warn_sent_as_a_reply_targets_the_replied_author(dispatcher):
    dp, bot, mock_client = dispatcher
    update = make_reply_update(21, COMMUNITY_GROUP_ID, user_id=715, text="/warn spam", replied_user_id=42)

    await dp.feed_update(bot, update)

    mock_client.create_warning.assert_called_once()
    assert mock_client.create_warning.call_args.kwargs["user_id"] == 42


@pytest.mark.asyncio
async def test_private_question_sent_as_a_reply_is_still_answered(dispatcher):
    dp, bot, mock_client = dispatcher
    mock_client.query.return_value = {"answer": "Open Settings, then Export."}
    update = make_reply_update(
        22, 12345, user_id=721, text="How do I export my wallet?", replied_user_id=999,
        replied_is_bot=True, chat_type="private",
    )

    await dp.feed_update(bot, update)

    mock_client.query.assert_called_once()
    assert mock_client.query.call_args.kwargs["query"] == "How do I export my wallet?"


@pytest.mark.asyncio
async def test_agent_reply_inside_the_support_group_still_resolves_the_ticket(dispatcher, monkeypatch):
    dp, bot, mock_client = dispatcher
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", SUPPORT_GROUP_ID)
    mock_client.get_ticket_by_support_message.return_value = {"id": 5, "user_id": 42}
    mock_client.resolve_ticket.return_value = {"id": 5, "user_id": 42, "is_newly_resolved": True}
    update = make_reply_update(
        23, SUPPORT_GROUP_ID, user_id=731, text="Restart the app and try again.", replied_user_id=1,
        replied_is_bot=True,
    )

    await dp.feed_update(bot, update)

    mock_client.resolve_ticket.assert_called_once()
    assert mock_client.resolve_ticket.call_args.kwargs["ticket_id"] == 5


@pytest.mark.parametrize("command_text,user_id", [("/BTC", 511), ("/Btc", 512), ("/btc", 513)])
@pytest.mark.asyncio
async def test_crypto_commands_are_case_insensitive(dispatcher, command_text, user_id):
    dp, bot, mock_client = dispatcher
    mock_client.get_crypto_price.return_value = {
        "symbol": "btc", "price_usd": 1.0, "change_24h_pct": 0.0,
        "market_cap_usd": 1.0, "volume_24h_usd": 1.0,
    }
    update = make_command_update(30, 12345, user_id=user_id, command_text=command_text, chat_type="private")

    await dp.feed_update(bot, update)

    mock_client.get_crypto_price.assert_called_once_with("btc")
