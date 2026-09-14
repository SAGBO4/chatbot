import asyncio
import logging
from aiogram import Bot, Dispatcher
from typing import Optional
from backend.config import settings
from bot.api_client import BackendClient
from bot.handlers.user_handlers import user_router
from bot.handlers.support_handlers import support_router
from bot.middlewares.throttling import ThrottlingMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")


def create_dispatcher(
    backend_client: Optional[BackendClient] = None,
    throttling_middleware: Optional[ThrottlingMiddleware] = None,
) -> Dispatcher:
    dp = Dispatcher()
    if backend_client is not None:
        dp["backend_client"] = backend_client

    throttler = throttling_middleware or ThrottlingMiddleware()
    dp.message.middleware(throttler)

    dp.include_router(user_router)
    dp.include_router(support_router)
    return dp


async def main():
    if getattr(settings, "SENTRY_DSN", None):
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=1.0)
            logger.info("Sentry monitoring initialized for Telegram Bot.")
        except ImportError:
            logger.warning("SENTRY_DSN is configured but sentry_sdk is not installed.")

    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "placeholder_token":
        logger.error(
            "TELEGRAM_BOT_TOKEN is not configured or set to placeholder. Please configure your .env file."
        )
        return

    backend_client = BackendClient()
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = create_dispatcher(backend_client=backend_client)

    logger.info("Starting Telegram Bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await backend_client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
