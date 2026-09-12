import asyncio
import logging
from aiogram import Bot, Dispatcher
from backend.config import settings
from bot.handlers.user_handlers import user_router
from bot.handlers.support_handlers import support_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(user_router)
    dp.include_router(support_router)
    return dp


async def main():
    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "placeholder_token":
        logger.warning(
            "TELEGRAM_BOT_TOKEN is not set or set to placeholder. Please configure your .env file."
        )

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = create_dispatcher()

    logger.info("Starting Telegram Bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
