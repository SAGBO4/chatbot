"""Sending or editing Telegram messages that contain Markdown built from untrusted text."""
import logging
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


async def call_with_markdown_fallback(
    send: Callable[..., Awaitable[Any]],
    *args: Any,
    what: str,
    plain_overrides: Optional[dict] = None,
    swallow_failure: bool = False,
    failure_level: int = logging.WARNING,
    **kwargs: Any,
) -> Any:
    """
    Call `send(*args, parse_mode="Markdown", **kwargs)`; if Telegram rejects the message, retry once without Markdown.

    Text built from user or agent input can contain characters Telegram refuses to parse, and losing the
    message is worse than showing it unformatted. `plain_overrides` replaces some keyword arguments in the
    retry (e.g. a plain-text version of `text`). If the retry fails as well, the error is raised, or with
    `swallow_failure` logged at `failure_level` and None returned (for best-effort messages such as editing
    a keyboard away). `what` names the message in the logs.
    """
    try:
        return await send(*args, parse_mode="Markdown", **kwargs)
    except Exception as exc:
        logger.warning("%s failed in Markdown, retrying in plain text: %s", what, exc)
    try:
        return await send(*args, **{**kwargs, **(plain_overrides or {})})
    except Exception as exc:
        if not swallow_failure:
            raise
        logger.log(failure_level, "%s failed in plain text too: %s", what, exc)
        return None
