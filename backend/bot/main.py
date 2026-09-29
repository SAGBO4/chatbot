import asyncio
import logging
from aiogram import Bot, Dispatcher
from typing import Optional
from app.config import settings
from app.observability import setup_observability
from app.services.crypto_service import SYMBOL_TO_COINGECKO_ID
from bot.api_client import BackendClient
from bot.handlers.user_handlers import user_router
from bot.handlers.support_handlers import support_router
from bot.handlers.community_handlers import community_router
from bot.handlers.moderation_handlers import moderation_router
from bot.handlers.crypto_handlers import crypto_router
from bot.handlers.setup_handlers import setup_router
from bot.middlewares.throttling import ThrottlingMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

# Short descriptions for Telegram's "/" command menu (native autocomplete/filtering), by language.
# Kept separate from app/i18n.py: this is metadata Telegram itself displays while typing, not a
# message the bot writes, and Telegram caps each description at 256 plain-text characters.
_COMMAND_DESCRIPTIONS = {
    "fr": {
        "start": "Démarrer / accueil",
        "help": "Afficher l'aide",
        "list": "Afficher la liste des commandes",
        "webapp": "Ouvrir la Mini App Support",
        "ask": "Poser une question dans le groupe",
        "setup_community": "Définir ce groupe comme groupe communautaire",
        "language": "Changer la langue du bot (fr|en)",
        "whitelist": "Gérer les admins whitelistés (owner uniquement)",
        "mute": "Rendre un membre muet",
        "unmute": "Lever le mute d'un membre",
        "ban": "Bannir un membre",
        "kick": "Expulser un membre",
        "warn": "Avertir un membre",
        "purge": "Supprimer les dernières réponses du bot",
    },
    "en": {
        "start": "Start / welcome",
        "help": "Show help",
        "list": "Show the list of commands",
        "webapp": "Open Support Mini App",
        "ask": "Ask a question in the group",
        "setup_community": "Set this group as the community group",
        "language": "Change the bot's language (fr|en)",
        "whitelist": "Manage whitelisted admins (owner only)",
        "mute": "Mute a member",
        "unmute": "Unmute a member",
        "ban": "Ban a member",
        "kick": "Kick a member",
        "warn": "Warn a member",
        "purge": "Delete the bot's latest answers",
    },
}

# Live crypto price commands (/btc, /eth, ...) share one description per language.
_CRYPTO_DESCRIPTION = {"fr": "Prix en direct de {symbol}", "en": "Live price of {symbol}"}

_DEFAULT_SCOPE_COMMANDS = ["start", "help", "list", "webapp"]
_PRIVATE_SCOPE_COMMANDS = ["start", "help", "list", "webapp"]
_GROUP_SCOPE_COMMANDS = ["help", "list", "ask"]
_ADMIN_SCOPE_COMMANDS = [
    "help",
    "list",
    "ask",
    "setup_community",
    "language",
    "mute",
    "unmute",
    "ban",
    "kick",
    "warn",
    "purge",
]
_OWNER_PRIVATE_SCOPE_COMMANDS = [
    "start",
    "help",
    "list",
    "webapp",
    "language",
    "whitelist",
]

# Telegram caps a command menu at 100 entries per scope, and SYMBOL_TO_COINGECKO_ID has over 100
# tickers, so only the best-known ones are listed in the "/" suggestion menu. Every crypto command
# still works when typed in full either way (see crypto_handlers.py, which registers one per ticker
# in SYMBOL_TO_COINGECKO_ID) - this only trims what the menu suggests while typing.
_MENU_CRYPTO_SYMBOLS = [
    "btc", "eth", "usdt", "bnb", "sol", "xrp", "doge", "ada", "ltc", "firo",
    "trx", "matic", "dot", "avax", "link", "atom", "xlm", "bch", "xmr", "ton",
    "shib", "uni", "near", "apt", "arb", "op", "sui", "icp", "fil", "pepe",
    "epic",
]


def _build_commands(command_names, lang: str = "fr"):
    """BotCommand list for `command_names` (skipping ones with no description), plus the menu's crypto symbols."""
    from aiogram.types import BotCommand

    descriptions = _COMMAND_DESCRIPTIONS.get(lang, _COMMAND_DESCRIPTIONS["fr"])
    commands = [
        BotCommand(command=name, description=descriptions[name])
        for name in command_names
        if name in descriptions
    ]
    crypto_template = _CRYPTO_DESCRIPTION.get(lang, _CRYPTO_DESCRIPTION["fr"])
    for symbol in _MENU_CRYPTO_SYMBOLS:
        if symbol in SYMBOL_TO_COINGECKO_ID:
            commands.append(BotCommand(command=symbol, description=crypto_template.format(symbol=symbol.upper())))
    return commands


async def configure_command_suggestions(bot: Bot) -> None:
    """
    Registers Telegram's native "/" command menu across all scopes:
    - Default (universal fallback)
    - AllPrivateChats (for standard members in DM)
    - AllGroupChats (for standard members in groups)
    - AllChatAdministrators (for group administrators)
    - Chat(chat_id=settings.BOT_OWNER_TELEGRAM_ID) (for the bot owner in private DM)
    Registered for universal fallback (language_code=None) as well as French and English.
    """
    from aiogram.types import (
        BotCommandScopeDefault,
        BotCommandScopeAllPrivateChats,
        BotCommandScopeAllGroupChats,
        BotCommandScopeAllChatAdministrators,
        BotCommandScopeChat,
    )

    scope_configs = [
        (BotCommandScopeDefault(), _DEFAULT_SCOPE_COMMANDS),
        (BotCommandScopeAllPrivateChats(), _PRIVATE_SCOPE_COMMANDS),
        (BotCommandScopeAllGroupChats(), _GROUP_SCOPE_COMMANDS),
        (BotCommandScopeAllChatAdministrators(), _ADMIN_SCOPE_COMMANDS),
    ]

    owner_id = settings.BOT_OWNER_TELEGRAM_ID
    if owner_id and owner_id > 0:
        scope_configs.append(
            (BotCommandScopeChat(chat_id=owner_id), _OWNER_PRIVATE_SCOPE_COMMANDS)
        )

    for scope, command_names in scope_configs:
        try:
            # Universal fallback (no language_code set)
            await bot.set_my_commands(
                _build_commands(command_names, "fr"),
                scope=scope,
                language_code=None,
            )
            # Specific language configurations
            for lang in ("fr", "en"):
                await bot.set_my_commands(
                    _build_commands(command_names, lang),
                    scope=scope,
                    language_code=lang,
                )
        except Exception as exc:
            if isinstance(scope, BotCommandScopeChat):
                logger.warning(
                    "Could not set commands for owner chat %s (chat may not be started yet): %s",
                    owner_id,
                    exc,
                )
            else:
                raise


def create_dispatcher(
    backend_client: Optional[BackendClient] = None,
    throttling_middleware: Optional[ThrottlingMiddleware] = None,
) -> Dispatcher:
    """Build the dispatcher: shared backend client, throttling on messages and button clicks, and the routers."""
    dp = Dispatcher()
    if backend_client is not None:
        dp["backend_client"] = backend_client

    throttler = throttling_middleware or ThrottlingMiddleware()
    dp.message.middleware(throttler)
    # Button clicks call the backend like messages do: throttle them too, or a user could bypass
    # the message throttling by rapid-clicking a button.
    dp.callback_query.middleware(throttler)

    # Command routers come before user_router, whose handle_user_query matches any text in a private
    # chat and would otherwise swallow "/btc", "/mute", etc.
    dp.include_router(setup_router)
    dp.include_router(support_router)
    dp.include_router(community_router)
    dp.include_router(moderation_router)
    dp.include_router(crypto_router)
    dp.include_router(user_router)
    return dp


async def main():
    """Entry point: log redaction and optional Sentry, refuse to start without a bot token, set the WebApp menu button, then poll."""
    setup_observability("Telegram Bot")

    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "placeholder_token":  # nosec B105
        logger.error(
            "TELEGRAM_BOT_TOKEN is not configured or set to placeholder. Please configure your .env file."
        )
        return

    backend_client = BackendClient()
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = create_dispatcher(backend_client=backend_client)

    try:
        await configure_command_suggestions(bot)
        logger.info("Telegram command suggestions configured.")
    except Exception as exc:
        logger.warning("Failed to configure Telegram command suggestions: %s", exc)

    # Telegram only accepts an https:// URL for the menu button
    webapp_url = settings.TELEGRAM_WEBAPP_URL
    if webapp_url and webapp_url.startswith("https://"):
        try:
            from aiogram.types import MenuButtonWebApp, WebAppInfo
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Support",
                    web_app=WebAppInfo(url=webapp_url),
                )
            )
            logger.info("Telegram WebApp Menu Button configured: %s", webapp_url)
        except Exception as exc:
            logger.warning("Failed to configure WebApp Menu Button: %s", exc)

    logger.info("Starting Telegram Bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await backend_client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
