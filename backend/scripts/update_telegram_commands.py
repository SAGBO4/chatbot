#!/usr/bin/env python3
"""
Registers the Telegram bot commands immediately with the Telegram Bot API.

Usage:
    python backend/scripts/update_telegram_commands.py
    # or inside backend/:
    python -m scripts.update_telegram_commands
"""
import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path so imports work when executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from aiogram import Bot
from app.config import settings
from bot.main import configure_command_suggestions


async def main() -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token == "placeholder_token":  # nosec B105
        print("❌ Error: TELEGRAM_BOT_TOKEN is not configured in .env.")
        sys.exit(1)

    print("🚀 Registering bot commands with Telegram Bot API...")
    bot = Bot(token=token)
    try:
        await configure_command_suggestions(bot)
        print("✅ Successfully registered all command scopes with Telegram:")
        print("   • Default scope (universal fallback, fr, en)")
        print("   • AllPrivateChats scope (standard DM members: /start, /help, /list, /webapp, crypto)")
        print("   • AllGroupChats scope (standard group members: /help, /list, /ask, /webapp, crypto)")
        print("   • AllChatAdministrators scope (group admins: /help, /list, /ask, /webapp, moderation, setup, crypto)")
        if settings.BOT_OWNER_TELEGRAM_ID and settings.BOT_OWNER_TELEGRAM_ID > 0:
            print(f"   • Chat scope for Owner ({settings.BOT_OWNER_TELEGRAM_ID}: /start, /help, /list, /webapp, /language, /whitelist, crypto)")
    except Exception as exc:
        print(f"❌ Failed to register commands: {exc}")
        sys.exit(1)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
