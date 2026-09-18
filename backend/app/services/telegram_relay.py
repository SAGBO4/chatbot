import logging
from typing import Optional, Tuple, Union
import httpx
from app.config import settings
from bot.utils import truncate_telegram_text

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
    async def _send_telegram_message(cls, chat_id: Union[int, str], text: str, target_desc: str) -> bool:
        """Sends a message to a chat id with Markdown and automatic plain text fallback."""
        if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "placeholder_token":  # nosec B105
            logger.info("Telegram notification simulated (bot token unset): %s to %s", text, target_desc)  # nosemgrep
            return True

        safe_text = truncate_telegram_text(text)
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        client, owns_client = await cls._get_client()
        try:
            resp = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": safe_text,
                    "parse_mode": "Markdown",
                },
            )
            if resp.status_code != 200:
                logger.warning(
                    "Markdown send failed for %s (status %s: %s), retrying in plain text",
                    target_desc, resp.status_code, resp.text,
                )
                plain_resp = await client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": safe_text,
                    },
                )
                if plain_resp.status_code != 200:
                    logger.error(
                        "Failed to relay message to %s (status %s): %s",
                        target_desc, plain_resp.status_code, plain_resp.text,
                    )
                    return False
            return True
        except httpx.HTTPError as exc:
            logger.error("Failed to relay message to %s: %s", target_desc, exc)
            return False
        except Exception as exc:
            logger.error("Failed to relay message to %s: %s", target_desc, exc)
            return False
        finally:
            if owns_client:
                await client.aclose()

    @classmethod
    async def send_message_to_user(cls, user_id: int, text: str) -> bool:
        """Sends a message to a Telegram user using the Telegram Bot API."""
        return await cls._send_telegram_message(chat_id=user_id, text=text, target_desc=f"user {user_id}")

    @classmethod
    async def notify_support_group(cls, text: str) -> bool:
        """Posts a notification message to the Telegram Support Group."""
        group_id = settings.TELEGRAM_SUPPORT_GROUP_ID
        if not settings.support_group_is_configured():
            logger.info("Telegram group notification simulated: %s", text)
            return True

        return await cls._send_telegram_message(chat_id=group_id, text=text, target_desc="support group")
