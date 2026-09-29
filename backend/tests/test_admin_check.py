import pytest
from unittest.mock import AsyncMock, MagicMock
from bot import admin_check


@pytest.fixture(autouse=True)
def clear_cache():
    admin_check._admin_status_cache.clear()
    yield
    admin_check._admin_status_cache.clear()


@pytest.mark.asyncio
async def test_admin_user_returns_true():
    bot = AsyncMock()
    bot.get_chat_member.return_value = MagicMock(status="administrator")
    result = await admin_check.is_group_admin(bot, chat_id=-100, user_id=1)
    assert result is True


@pytest.mark.asyncio
async def test_creator_returns_true():
    bot = AsyncMock()
    bot.get_chat_member.return_value = MagicMock(status="creator")
    result = await admin_check.is_group_admin(bot, chat_id=-100, user_id=1)
    assert result is True


@pytest.mark.asyncio
async def test_member_returns_false():
    bot = AsyncMock()
    bot.get_chat_member.return_value = MagicMock(status="member")
    result = await admin_check.is_group_admin(bot, chat_id=-100, user_id=1)
    assert result is False


@pytest.mark.asyncio
async def test_api_error_returns_false():
    bot = AsyncMock()
    bot.get_chat_member.side_effect = Exception("network error")
    result = await admin_check.is_group_admin(bot, chat_id=-100, user_id=1)
    assert result is False


@pytest.mark.asyncio
async def test_result_is_cached_and_avoids_second_api_call():
    bot = AsyncMock()
    bot.get_chat_member.return_value = MagicMock(status="administrator")
    first = await admin_check.is_group_admin(bot, chat_id=-100, user_id=1)
    second = await admin_check.is_group_admin(bot, chat_id=-100, user_id=1)
    assert first is True
    assert second is True
    bot.get_chat_member.assert_called_once()


@pytest.mark.asyncio
async def test_different_users_are_cached_independently():
    bot = AsyncMock()
    bot.get_chat_member.side_effect = [
        MagicMock(status="administrator"),
        MagicMock(status="member"),
    ]
    admin_result = await admin_check.is_group_admin(bot, chat_id=-100, user_id=1)
    member_result = await admin_check.is_group_admin(bot, chat_id=-100, user_id=2)
    assert admin_result is True
    assert member_result is False
    assert bot.get_chat_member.call_count == 2


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache():
    bot = AsyncMock()
    bot.get_chat_member.return_value = MagicMock(status="administrator")
    await admin_check.is_group_admin(bot, chat_id=-100, user_id=1)
    await admin_check.is_group_admin(bot, chat_id=-100, user_id=1, force_refresh=True)
    assert bot.get_chat_member.call_count == 2


@pytest.mark.asyncio
async def test_invalidate_admin_cache_clears_entries():
    bot = AsyncMock()
    bot.get_chat_member.return_value = MagicMock(status="administrator")
    await admin_check.is_group_admin(bot, chat_id=-100, user_id=1)
    await admin_check.is_group_admin(bot, chat_id=-100, user_id=2)

    # Invalidate specific user
    admin_check.invalidate_admin_cache(chat_id=-100, user_id=1)
    await admin_check.is_group_admin(bot, chat_id=-100, user_id=1)
    # user 1 called again (2 calls total for user 1, 1 for user 2)
    assert bot.get_chat_member.call_count == 3

    # Invalidate all
    admin_check.invalidate_admin_cache()
    await admin_check.is_group_admin(bot, chat_id=-100, user_id=2)
    assert bot.get_chat_member.call_count == 4


@pytest.mark.asyncio
async def test_is_bot_admin_true_for_whitelisted_non_telegram_admin(monkeypatch):
    """A whitelisted user counts as a bot admin even without native Telegram admin rights."""
    monkeypatch.setattr(admin_check, "is_authorized", AsyncMock(return_value=True))
    bot = AsyncMock()
    bot.get_chat_member.return_value = MagicMock(status="member")
    result = await admin_check.is_bot_admin(bot, chat_id=-100, user_id=1)
    assert result is True
    bot.get_chat_member.assert_not_called()


@pytest.mark.asyncio
async def test_is_bot_admin_true_for_native_telegram_admin(monkeypatch):
    """A native Telegram group admin counts as a bot admin even without being whitelisted."""
    monkeypatch.setattr(admin_check, "is_authorized", AsyncMock(return_value=False))
    bot = AsyncMock()
    bot.get_chat_member.return_value = MagicMock(status="administrator")
    result = await admin_check.is_bot_admin(bot, chat_id=-100, user_id=1)
    assert result is True


@pytest.mark.asyncio
async def test_is_bot_admin_false_when_neither_whitelisted_nor_telegram_admin(monkeypatch):
    monkeypatch.setattr(admin_check, "is_authorized", AsyncMock(return_value=False))
    bot = AsyncMock()
    bot.get_chat_member.return_value = MagicMock(status="member")
    result = await admin_check.is_bot_admin(bot, chat_id=-100, user_id=1)
    assert result is False
