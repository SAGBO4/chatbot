import logging
from typing import Optional, Tuple
import httpx
from backend.config import settings

logger = logging.getLogger(__name__)


class TelegramRelay:
    _shared_client: Optional[httpx.AsyncClient] = None

    @classmethod
    def set_shared_client(cls, client: Optional[httpx.AsyncClient]) -> None:
        """Configures a shared persistent httpx client for Telegram relay operations."""
        cls._shared_client = client

    @classmethod
    async def _get_client(cls) -> Tuple[httpx.AsyncClient, bool]:
        """Returns the shared client or creates a temporary one if unconfigured."""
        if cls._shared_client is not None and not cls._shared_client.is_closed:
            return cls._shared_client, False
        return httpx.AsyncClient(timeout=10.0), True

    @classmethod
    async def send_message_to_user(cls, user_id: int, text: str) -> bool:
        """Sends a message to a Telegram user using the Telegram Bot API."""
        if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "placeholder_token":
            logger.info("Telegram notification simulated (token not configured): %s to user %s", text, user_id)
            return True

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        client, owns_client = await cls._get_client()
        try:
            resp = await client.post(
                url,
                json={
                    "chat_id": user_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
            return resp.status_code == 200
        except httpx.HTTPError as exc:
            logger.error("Failed to relay message to Telegram user %s: %s", user_id, exc)
            return False
        except Exception as exc:
            logger.error("Failed to relay message to Telegram user %s: %s", user_id, exc)
            return False
        finally:
            if owns_client:
                await client.aclose()

    @classmethod
    async def notify_support_group(cls, text: str) -> bool:
        """Posts a notification message to the Telegram Support Group."""
        group_id = settings.TELEGRAM_SUPPORT_GROUP_ID
        if not settings.support_group_is_configured():
            logger.info("Telegram group notification simulated: %s", text)
            return True

        if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "placeholder_token":
            logger.info("Telegram group notification simulated (token not configured): %s", text)
            return True

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        client, owns_client = await cls._get_client()
        try:
            resp = await client.post(
                url,
                json={
                    "chat_id": group_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
            return resp.status_code == 200
        except httpx.HTTPError as exc:
            logger.error("Failed to notify Telegram support group: %s", exc)
            return False
        except Exception as exc:
            logger.error("Failed to notify Telegram support group: %s", exc)
            return False
        finally:
            if owns_client:
                await client.aclose()
