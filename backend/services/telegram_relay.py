import logging
from typing import Optional
import httpx
from backend.config import settings

logger = logging.getLogger(__name__)


class TelegramRelay:
    @staticmethod
    async def send_message_to_user(user_id: int, text: str) -> bool:
        """Sends a message to a Telegram user using the Telegram Bot API."""
        if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "placeholder_token":
            logger.info("Telegram notification simulated (token not configured): %s to user %s", text, user_id)
            return True

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    json={
                        "chat_id": user_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                )
                return resp.status_code == 200
        except Exception as exc:
            logger.error("Failed to relay message to Telegram user %s: %s", user_id, exc)
            return False

    @staticmethod
    async def notify_support_group(text: str) -> bool:
        """Posts a notification message to the Telegram Support Group."""
        group_id = settings.TELEGRAM_SUPPORT_GROUP_ID
        if not settings.support_group_is_configured():
            logger.info("Telegram group notification simulated: %s", text)
            return True

        if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "placeholder_token":
            logger.info("Telegram group notification simulated (token not configured): %s", text)
            return True

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    json={
                        "chat_id": group_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                )
                return resp.status_code == 200
        except Exception as exc:
            logger.error("Failed to notify Telegram support group: %s", exc)
            return False
