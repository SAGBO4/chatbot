import pytest
from unittest.mock import AsyncMock
from aiogram.types import (
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    BotCommandScopeChat,
)

from bot.main import (
    configure_command_suggestions,
    _build_commands,
    _MENU_CRYPTO_SYMBOLS,
    _DEFAULT_SCOPE_COMMANDS,
    _PRIVATE_SCOPE_COMMANDS,
    _GROUP_SCOPE_COMMANDS,
    _ADMIN_SCOPE_COMMANDS,
    _OWNER_PRIVATE_SCOPE_COMMANDS,
)
from app.config import settings
from app.services.crypto_service import SYMBOL_TO_COINGECKO_ID


@pytest.mark.asyncio
async def test_configure_command_suggestions_registers_all_scopes_including_owner(monkeypatch):
    monkeypatch.setattr(settings, "BOT_OWNER_TELEGRAM_ID", 6149977795)
    bot = AsyncMock()

    await configure_command_suggestions(bot)

    assert bot.set_my_commands.call_count == 15
    scopes_and_langs = {
        (type(call.kwargs["scope"]), call.kwargs["language_code"])
        for call in bot.set_my_commands.call_args_list
    }
    assert scopes_and_langs == {
        (BotCommandScopeDefault, None),
        (BotCommandScopeDefault, "fr"),
        (BotCommandScopeDefault, "en"),
        (BotCommandScopeAllPrivateChats, None),
        (BotCommandScopeAllPrivateChats, "fr"),
        (BotCommandScopeAllPrivateChats, "en"),
        (BotCommandScopeAllGroupChats, None),
        (BotCommandScopeAllGroupChats, "fr"),
        (BotCommandScopeAllGroupChats, "en"),
        (BotCommandScopeAllChatAdministrators, None),
        (BotCommandScopeAllChatAdministrators, "fr"),
        (BotCommandScopeAllChatAdministrators, "en"),
        (BotCommandScopeChat, None),
        (BotCommandScopeChat, "fr"),
        (BotCommandScopeChat, "en"),
    }


@pytest.mark.asyncio
async def test_configure_command_suggestions_without_owner_id(monkeypatch):
    monkeypatch.setattr(settings, "BOT_OWNER_TELEGRAM_ID", 0)
    bot = AsyncMock()

    await configure_command_suggestions(bot)

    assert bot.set_my_commands.call_count == 12
    scopes_and_langs = {
        (type(call.kwargs["scope"]), call.kwargs["language_code"])
        for call in bot.set_my_commands.call_args_list
    }
    assert scopes_and_langs == {
        (BotCommandScopeDefault, None),
        (BotCommandScopeDefault, "fr"),
        (BotCommandScopeDefault, "en"),
        (BotCommandScopeAllPrivateChats, None),
        (BotCommandScopeAllPrivateChats, "fr"),
        (BotCommandScopeAllPrivateChats, "en"),
        (BotCommandScopeAllGroupChats, None),
        (BotCommandScopeAllGroupChats, "fr"),
        (BotCommandScopeAllGroupChats, "en"),
        (BotCommandScopeAllChatAdministrators, None),
        (BotCommandScopeAllChatAdministrators, "fr"),
        (BotCommandScopeAllChatAdministrators, "en"),
    }


def test_build_commands_includes_the_menu_crypto_symbols():
    commands = _build_commands(["start", "help", "list"], "fr")
    command_names = {c.command for c in commands}

    assert "start" in command_names
    assert "help" in command_names
    assert "list" in command_names
    for symbol in _MENU_CRYPTO_SYMBOLS:
        assert symbol in command_names


def test_menu_crypto_symbols_are_all_valid_and_stay_under_telegrams_100_command_cap():
    """
    Telegram rejects set_my_commands past 100 entries per scope, and SYMBOL_TO_COINGECKO_ID has more
    than 100 tickers, so the menu must only ever list a bounded subset of them (every ticker still
    works as a command when typed in full - see crypto_handlers.py).
    """
    assert all(symbol in SYMBOL_TO_COINGECKO_ID for symbol in _MENU_CRYPTO_SYMBOLS)
    for command_names in (
        _DEFAULT_SCOPE_COMMANDS,
        _PRIVATE_SCOPE_COMMANDS,
        _GROUP_SCOPE_COMMANDS,
        _ADMIN_SCOPE_COMMANDS,
        _OWNER_PRIVATE_SCOPE_COMMANDS,
    ):
        assert len(command_names) + len(_MENU_CRYPTO_SYMBOLS) <= 100


def test_build_commands_skips_unknown_command_names():
    commands = _build_commands(["start", "not_a_real_command"], "en")
    command_names = {c.command for c in commands}

    assert "start" in command_names
    assert "not_a_real_command" not in command_names


def test_command_scope_lists_strict_partitioning():
    """Verify that command scope lists strictly separate regular member vs admin vs owner commands."""
    # Standard group members: help, list, ask, webapp (no admin, no setup, no owner)
    assert set(_GROUP_SCOPE_COMMANDS) == {"help", "list", "ask", "webapp"}
    forbidden_in_group = {"mute", "unmute", "ban", "kick", "warn", "purge", "setup_community", "language", "whitelist"}
    assert not any(cmd in _GROUP_SCOPE_COMMANDS for cmd in forbidden_in_group)

    # Standard private DM members: start, help, list, webapp (no whitelist, no language, no setup_community, no moderation)
    assert set(_PRIVATE_SCOPE_COMMANDS) == {"start", "help", "list", "webapp"}
    forbidden_in_dm = {"whitelist", "language", "setup_community", "mute", "unmute", "ban", "kick", "warn", "purge", "ask"}
    assert not any(cmd in _PRIVATE_SCOPE_COMMANDS for cmd in forbidden_in_dm)

    # Admins in groups: moderation + setup, but NOT owner-only whitelist
    admin_set = set(_ADMIN_SCOPE_COMMANDS)
    assert {"help", "list", "ask", "webapp", "setup_community", "language", "mute", "unmute", "ban", "kick", "warn", "purge"} == admin_set
    assert "whitelist" not in admin_set

    # Owner in private DM: whitelist and language
    owner_set = set(_OWNER_PRIVATE_SCOPE_COMMANDS)
    assert {"start", "help", "list", "webapp", "language", "whitelist"} == owner_set


@pytest.mark.asyncio
async def test_configure_command_suggestions_exact_commands_per_scope(monkeypatch):
    """Verify the exact commands passed to set_my_commands for each scope in configure_command_suggestions."""
    owner_id = 6149977795
    monkeypatch.setattr(settings, "BOT_OWNER_TELEGRAM_ID", owner_id)
    bot = AsyncMock()

    await configure_command_suggestions(bot)

    # Group commands passed to set_my_commands by scope
    scope_to_commands = {}
    for call in bot.set_my_commands.call_args_list:
        scope = call.kwargs["scope"]
        lang = call.kwargs["language_code"]
        commands = call.args[0] if call.args else call.kwargs["commands"]
        command_names = [c.command for c in commands]
        scope_to_commands[(type(scope), getattr(scope, "chat_id", None), lang)] = command_names

    # 1. Standard member in group (BotCommandScopeAllGroupChats)
    group_cmds_fr = scope_to_commands[(BotCommandScopeAllGroupChats, None, "fr")]
    assert "help" in group_cmds_fr
    assert "list" in group_cmds_fr
    assert "ask" in group_cmds_fr
    assert "webapp" in group_cmds_fr
    assert "btc" in group_cmds_fr
    for forbidden in ("mute", "unmute", "ban", "kick", "warn", "purge", "whitelist", "setup_community", "language"):
        assert forbidden not in group_cmds_fr

    # 2. Standard member in DM (BotCommandScopeAllPrivateChats)
    dm_cmds_fr = scope_to_commands[(BotCommandScopeAllPrivateChats, None, "fr")]
    assert "start" in dm_cmds_fr
    assert "help" in dm_cmds_fr
    assert "list" in dm_cmds_fr
    assert "webapp" in dm_cmds_fr
    assert "btc" in dm_cmds_fr
    for forbidden in ("whitelist", "language", "setup_community", "mute", "unmute", "ban", "kick", "warn", "purge", "ask"):
        assert forbidden not in dm_cmds_fr

    # 3. Admins (BotCommandScopeAllChatAdministrators)
    admin_cmds_fr = scope_to_commands[(BotCommandScopeAllChatAdministrators, None, "fr")]
    for allowed in ("help", "list", "ask", "webapp", "setup_community", "language", "mute", "unmute", "ban", "kick", "warn", "purge", "btc"):
        assert allowed in admin_cmds_fr
    assert "whitelist" not in admin_cmds_fr

    # 4. Owner DM (BotCommandScopeChat)
    owner_cmds_fr = scope_to_commands[(BotCommandScopeChat, owner_id, "fr")]
    for allowed in ("start", "help", "list", "webapp", "language", "whitelist", "btc"):
        assert allowed in owner_cmds_fr

