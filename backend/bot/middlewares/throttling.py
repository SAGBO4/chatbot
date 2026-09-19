import time
import logging
from typing import Any, Awaitable, Callable, Dict, List
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

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
        self._next_prune = 0.0

    def _prune(self, now: float) -> None:
        """
        Forget users idle for longer than the window, at most once per window.

        Without this both dicts grow with every user the bot has ever seen. Dropping an idle entry
        changes nothing for that user: their next message would start from an empty window anyway.
        """
        if now < self._next_prune:
            return
        self._next_prune = now + self.window_seconds
        window_start = now - self.window_seconds
        for user_id in [uid for uid, stamps in self.user_timestamps.items() if not stamps or stamps[-1] <= window_start]:
            del self.user_timestamps[user_id]
        for user_id in [uid for uid, warned in self.last_warning_time.items() if now - warned >= self.warning_cooldown]:
            del self.last_warning_time[user_id]

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        user = event.from_user
        if not user:
            return await handler(event, data)

        user_id = user.id
        now = time.time()
        self._prune(now)
        window_start = now - self.window_seconds

        current_timestamps = [t for t in self.user_timestamps.get(user_id, []) if t > window_start]

        if len(current_timestamps) >= self.rate_limit:
            logger.warning("Throttling rate limit reached for user %s (%s messages in %ss)", user_id, len(current_timestamps), self.window_seconds)

            last_warn = self.last_warning_time.get(user_id, 0.0)
            if now - last_warn >= self.warning_cooldown:
                self.last_warning_time[user_id] = now
                try:
                    if isinstance(event, CallbackQuery):
                        # A toast, not a new message: callback queries are answered with .answer(text=...)
                        await event.answer(
                            "⚠️ Veuillez patienter quelques secondes avant de réessayer.",
                            show_alert=False,
                        )
                    else:
                        await event.answer("⚠️ Veuillez patienter quelques secondes avant d'envoyer un nouveau message.")
                except Exception as exc:
                    logger.warning("Failed to send throttling notice to user %s: %s", user_id, exc)
            return None

        current_timestamps.append(now)
        self.user_timestamps[user_id] = current_timestamps
        return await handler(event, data)
