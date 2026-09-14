import asyncio
import logging
from aiogram import Bot, Dispatcher
from typing import Optional
from backend.config import settings
from bot.api_client import BackendClient
from bot.handlers.user_handlers import user_router
from bot.handlers.support_handlers import support_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")


def create_dispatcher(backend_client: Optional[BackendClient] = None) -> Dispatcher:
    dp = Dispatcher()
    if backend_client is not None:
        dp["backend_client"] = backend_client
    dp.include_router(user_router)
    dp.include_router(support_router)
    return dp


async def main():
    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "placeholder_token":
        logger.warning(
            "TELEGRAM_BOT_TOKEN is not set or set to placeholder. Please configure your .env file."
        )

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
