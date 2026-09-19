import asyncio
import logging
from aiogram import Bot, Dispatcher
from typing import Optional
from app.config import settings
from app.observability import setup_observability
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

    # Telegram only accepts an https:// URL for the menu button
    webapp_url = getattr(settings, "TELEGRAM_WEBAPP_URL", None)
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
