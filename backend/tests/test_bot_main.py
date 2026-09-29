import pytest
from unittest.mock import AsyncMock
from aiogram.types import BotCommandScopeAllGroupChats, BotCommandScopeDefault

from bot.main import (
    configure_command_suggestions,
    _build_commands,
    _MENU_CRYPTO_SYMBOLS,
    _DEFAULT_SCOPE_COMMANDS,
    _GROUP_SCOPE_COMMANDS,
)
from app.services.crypto_service import SYMBOL_TO_COINGECKO_ID


@pytest.mark.asyncio
async def test_configure_command_suggestions_registers_default_and_group_scopes_in_both_languages():
    bot = AsyncMock()

    await configure_command_suggestions(bot)

    assert bot.set_my_commands.call_count == 4
    scopes_and_langs = {
        (type(call.kwargs["scope"]), call.kwargs["language_code"])
        for call in bot.set_my_commands.call_args_list
    }
    assert scopes_and_langs == {
        (BotCommandScopeDefault, "fr"),
        (BotCommandScopeDefault, "en"),
        (BotCommandScopeAllGroupChats, "fr"),
        (BotCommandScopeAllGroupChats, "en"),
    }


def test_build_commands_includes_the_menu_crypto_symbols():
    commands = _build_commands(["start", "help"], "fr")
    command_names = {c.command for c in commands}

    assert "start" in command_names
    assert "help" in command_names
    for symbol in _MENU_CRYPTO_SYMBOLS:
        assert symbol in command_names


def test_menu_crypto_symbols_are_all_valid_and_stay_under_telegrams_100_command_cap():
    """
    Telegram rejects set_my_commands past 100 entries per scope, and SYMBOL_TO_COINGECKO_ID has more
    than 100 tickers, so the menu must only ever list a bounded subset of them (every ticker still
    works as a command when typed in full - see crypto_handlers.py).
    """
    assert all(symbol in SYMBOL_TO_COINGECKO_ID for symbol in _MENU_CRYPTO_SYMBOLS)
    for command_names in (_DEFAULT_SCOPE_COMMANDS, _GROUP_SCOPE_COMMANDS):
        assert len(command_names) + len(_MENU_CRYPTO_SYMBOLS) <= 100


def test_build_commands_skips_unknown_command_names():
    commands = _build_commands(["start", "not_a_real_command"], "en")
    command_names = {c.command for c in commands}

    assert "start" in command_names
    assert "not_a_real_command" not in command_names
