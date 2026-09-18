import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import User, Chat, Message
from aiogram.filters import CommandObject

from bot.handlers import moderation_handlers
from bot.handlers.moderation_handlers import (
    handle_mute,
    handle_unmute,
    handle_ban,
    handle_kick,
    handle_warn,
)

COMMUNITY_GROUP_ID = -100555111
OTHER_CHAT_ID = -100999999


async def _fake_get_community_group_id(backend_client=None):
    return COMMUNITY_GROUP_ID


@pytest.fixture(autouse=True)
def configure_community_group(monkeypatch):
    monkeypatch.setattr("bot.group_scope.get_community_group_id", _fake_get_community_group_id)


def make_admin_message(chat_id, admin_id, text, reply_to=None):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=chat_id, type="supergroup")
    message.from_user = MagicMock(spec=User, id=admin_id, username="admin_x", first_name="Admin")
    message.text = text
    message.reply_to_message = reply_to
    message.reply = AsyncMock()
    return message


def make_target_reply(target_id, username="bob"):
    target_message = MagicMock(spec=Message)
    target_message.from_user = MagicMock(spec=User, id=target_id, username=username, first_name="Bob")
    return target_message


def command_object(args=None):
    return CommandObject(prefix="/", command="mute", args=args)


@pytest.mark.asyncio
async def test_mute_rejected_for_non_admin(monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return False
    monkeypatch.setattr(moderation_handlers, "is_group_admin", fake_is_admin)

    reply_to = make_target_reply(target_id=55)
    message = make_admin_message(COMMUNITY_GROUP_ID, admin_id=1, text="/mute", reply_to=reply_to)
    bot = AsyncMock()

    await handle_mute(message, command_object(), bot)

    bot.restrict_chat_member.assert_not_called()
    message.reply.assert_called_once()
    assert "administrateurs" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_mute_outside_community_group_is_ignored(monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return True
    monkeypatch.setattr(moderation_handlers, "is_group_admin", fake_is_admin)

    reply_to = make_target_reply(target_id=55)
    message = make_admin_message(OTHER_CHAT_ID, admin_id=1, text="/mute", reply_to=reply_to)
    bot = AsyncMock()

    await handle_mute(message, command_object(), bot)

    bot.restrict_chat_member.assert_not_called()
    message.reply.assert_not_called()


@pytest.mark.asyncio
async def test_mute_by_reply_with_duration(monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return True
    monkeypatch.setattr(moderation_handlers, "is_group_admin", fake_is_admin)

    reply_to = make_target_reply(target_id=55)
    message = make_admin_message(COMMUNITY_GROUP_ID, admin_id=1, text="/mute 3600", reply_to=reply_to)
    bot = AsyncMock()

    await handle_mute(message, CommandObject(prefix="/", command="mute", args="3600"), bot)

    bot.restrict_chat_member.assert_called_once()
    kwargs = bot.restrict_chat_member.call_args.kwargs
    assert kwargs["user_id"] == 55
    assert kwargs["chat_id"] == COMMUNITY_GROUP_ID
    assert kwargs["until_date"] is not None
    message.reply.assert_called_once()
    assert "3600 secondes" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_mute_by_explicit_user_id_indefinite(monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return True
    monkeypatch.setattr(moderation_handlers, "is_group_admin", fake_is_admin)

    message = make_admin_message(COMMUNITY_GROUP_ID, admin_id=1, text="/mute 777")
    bot = AsyncMock()

    await handle_mute(message, CommandObject(prefix="/", command="mute", args="777"), bot)

    bot.restrict_chat_member.assert_called_once()
    kwargs = bot.restrict_chat_member.call_args.kwargs
    assert kwargs["user_id"] == 777
    assert kwargs["until_date"] is None
    assert "indéfiniment" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_mute_without_target_replies_error(monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return True
    monkeypatch.setattr(moderation_handlers, "is_group_admin", fake_is_admin)

    message = make_admin_message(COMMUNITY_GROUP_ID, admin_id=1, text="/mute")
    bot = AsyncMock()

    await handle_mute(message, CommandObject(prefix="/", command="mute", args=None), bot)

    bot.restrict_chat_member.assert_not_called()
    message.reply.assert_called_once()


@pytest.mark.asyncio
async def test_unmute_restores_permissions(monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return True
    monkeypatch.setattr(moderation_handlers, "is_group_admin", fake_is_admin)

    reply_to = make_target_reply(target_id=55)
    message = make_admin_message(COMMUNITY_GROUP_ID, admin_id=1, text="/unmute", reply_to=reply_to)
    bot = AsyncMock()

    await handle_unmute(message, CommandObject(prefix="/", command="unmute", args=None), bot)

    bot.restrict_chat_member.assert_called_once()
    kwargs = bot.restrict_chat_member.call_args.kwargs
    assert kwargs["permissions"].can_send_messages is True


@pytest.mark.asyncio
async def test_ban_calls_ban_chat_member(monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return True
    monkeypatch.setattr(moderation_handlers, "is_group_admin", fake_is_admin)

    reply_to = make_target_reply(target_id=55)
    message = make_admin_message(COMMUNITY_GROUP_ID, admin_id=1, text="/ban", reply_to=reply_to)
    bot = AsyncMock()

    await handle_ban(message, CommandObject(prefix="/", command="ban", args=None), bot)

    bot.ban_chat_member.assert_called_once_with(chat_id=COMMUNITY_GROUP_ID, user_id=55)


@pytest.mark.asyncio
async def test_kick_bans_then_unbans(monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return True
    monkeypatch.setattr(moderation_handlers, "is_group_admin", fake_is_admin)

    reply_to = make_target_reply(target_id=55)
    message = make_admin_message(COMMUNITY_GROUP_ID, admin_id=1, text="/kick", reply_to=reply_to)
    bot = AsyncMock()

    await handle_kick(message, CommandObject(prefix="/", command="kick", args=None), bot)

    bot.ban_chat_member.assert_called_once_with(chat_id=COMMUNITY_GROUP_ID, user_id=55)
    bot.unban_chat_member.assert_called_once_with(chat_id=COMMUNITY_GROUP_ID, user_id=55, only_if_banned=True)


@pytest.mark.asyncio
async def test_warn_records_via_backend_and_reports_total(monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return True
    monkeypatch.setattr(moderation_handlers, "is_group_admin", fake_is_admin)

    reply_to = make_target_reply(target_id=55)
    message = make_admin_message(COMMUNITY_GROUP_ID, admin_id=1, text="/warn spam", reply_to=reply_to)
    bot = AsyncMock()
    mock_client = AsyncMock()
    mock_client.create_warning.return_value = {"id": 1, "user_id": 55}
    mock_client.list_warnings.return_value = {"count": 2, "warnings": []}

    await handle_warn(
        message, CommandObject(prefix="/", command="warn", args="spam"), bot, backend_client=mock_client
    )

    mock_client.create_warning.assert_called_once_with(
        user_id=55, group_id=COMMUNITY_GROUP_ID, warned_by="admin_x", reason="spam"
    )
    assert "Total : 2" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_non_admin_cannot_warn(monkeypatch):
    async def fake_is_admin(bot, chat_id, user_id):
        return False
    monkeypatch.setattr(moderation_handlers, "is_group_admin", fake_is_admin)

    reply_to = make_target_reply(target_id=55)
    message = make_admin_message(COMMUNITY_GROUP_ID, admin_id=1, text="/warn spam", reply_to=reply_to)
    bot = AsyncMock()
    mock_client = AsyncMock()

    await handle_warn(
        message, CommandObject(prefix="/", command="warn", args="spam"), bot, backend_client=mock_client
    )

    mock_client.create_warning.assert_not_called()
