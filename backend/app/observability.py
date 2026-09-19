"""
Logging and Sentry setup shared by the API and the bot, with secrets redacted.

Two kinds of secret must never leave the process:
- query parameters such as `?token=...` (webhook secrets);
- the Telegram bot token, which is part of every Bot API URL (`/bot<token>/sendMessage`). httpx logs
  that URL at INFO level and Sentry records it as a breadcrumb, so it is redacted in both.
"""
import logging
import re
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_QUERY_SECRET_RE = re.compile(r"([?&](?:token|secret|api_key|password)=)[^&]+", re.IGNORECASE)
_BOT_TOKEN_RE = re.compile(r"(/bot)\d+:[A-Za-z0-9_-]+")


def sanitize_url_query(url: str) -> str:
    """Redact the values of sensitive query parameters (token, secret, api_key, password) in a URL."""
    return _QUERY_SECRET_RE.sub(r"\1[REDACTED]", url)


def redact_secrets(text: str) -> str:
    """Redact sensitive query parameters and Telegram bot tokens in a string."""
    return _BOT_TOKEN_RE.sub(r"\1[REDACTED]", sanitize_url_query(text))


class SensitiveDataFilter(logging.Filter):
    """
    Log filter that redacts secrets from the formatted message.

    It works on the formatted message because libraries pass URLs as objects (httpx logs
    `request.url`, not a string), which a per-argument check would miss.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        redacted = redact_secrets(message)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


def scrub(value: Any) -> Any:
    """Return `value` with secrets redacted in every string, recursing into dicts and lists."""
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def _scrub_event(event: Any, hint: Optional[dict] = None) -> Any:
    """Sentry `before_send` / `before_send_transaction` / `before_breadcrumb` hook."""
    return scrub(event)


def setup_observability(service: str) -> None:
    """
    Call once at startup: redact secrets in httpx's logs, and start Sentry when SENTRY_DSN is set.

    `service` only labels the log line ("Backend API", "Telegram Bot").
    """
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).addFilter(SensitiveDataFilter())

    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("SENTRY_DSN is configured but sentry_sdk is not installed.")
        return
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        before_send=_scrub_event,
        before_send_transaction=_scrub_event,
        before_breadcrumb=_scrub_event,
    )
    logger.info("Sentry monitoring initialized for %s.", service)
