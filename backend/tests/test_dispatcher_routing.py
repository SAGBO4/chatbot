import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from aiogram import Bot
from aiogram.types import Update, Message, Chat, User

from bot.main import create_dispatcher

COMMUNITY_GROUP_ID = -100555111
OTHER_GROUP_ID = -100999999


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


@pytest.mark.parametrize("command_text", ["/mute 999", "/unmute 999", "/ban 999", "/kick 999", "/warn 999 spam"])
@pytest.mark.asyncio
async def test_moderation_commands_do_not_route_outside_community_group(dispatcher, command_text):
    dp, bot, mock_client = dispatcher
    update = make_command_update(3, OTHER_GROUP_ID, user_id=1, command_text=command_text)

    await dp.feed_update(bot, update)

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
    mock_client.is_whitelisted.return_value = False

    async def no_group(backend_client=None):
        return None
    monkeypatch.setattr("bot.handlers.setup_handlers.get_community_group_id", no_group)

    update = make_command_update(6, 602, user_id=602, command_text="/start", chat_type="private")
    await dp.feed_update(bot, update)

    sent_text = bot.session.call_args.args[1].text
    assert "bienvenue" in sent_text.lower()
    assert "communautaire" not in sent_text
