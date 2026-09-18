import time
import logging
from typing import Any, Awaitable, Callable, Dict, List
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """
    In-memory throttling middleware restricting user messages to a maximum rate
    (default: 5 messages per 10 seconds) per user_id.

    Excess messages are dropped before executing handler logic or calling the backend,
    and a polite warning notification is sent to the user.
    """

    def __init__(
        self,
        rate_limit: int = 5,
        window_seconds: float = 10.0,
        warning_cooldown: float = 5.0,
    ):
        super().__init__()
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        self.warning_cooldown = warning_cooldown
        self.user_timestamps: Dict[int, List[float]] = {}
        self.last_warning_time: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user = event.from_user
        if not user:
            return await handler(event, data)

        user_id = user.id
        now = time.time()
        window_start = now - self.window_seconds

        # Clean timestamps older than sliding window
        current_timestamps = [t for t in self.user_timestamps.get(user_id, []) if t > window_start]

        if len(current_timestamps) >= self.rate_limit:
            # User exceeded rate limit
            logger.warning("Throttling rate limit reached for user %s (%s messages in %ss)", user_id, len(current_timestamps), self.window_seconds)
            
            # Send warning message if cooldown has elapsed
            last_warn = self.last_warning_time.get(user_id, 0.0)
            if now - last_warn >= self.warning_cooldown:
                self.last_warning_time[user_id] = now
                try:
                    await event.answer("⚠️ Veuillez patienter quelques secondes avant d'envoyer un nouveau message.")
                except Exception as exc:
                    logger.warning("Failed to send throttling notice to user %s: %s", user_id, exc)
            return None

        current_timestamps.append(now)
        self.user_timestamps[user_id] = current_timestamps
        return await handler(event, data)
