"""Text helpers for Telegram messages, shared by the API and the bot."""
import re
from typing import Optional

from app.i18n import DEFAULT_LANGUAGE, t

# Telegram rejects messages over 4096 characters; 4000 keeps a safety margin
TELEGRAM_MAX_MESSAGE_LENGTH = 4000


def escape_telegram_markdown(text: str) -> str:
    """Escapes legacy Telegram Markdown metacharacters in untrusted text."""
    return re.sub(r"([_*`\[])", r"\\\1", text)


def truncate_telegram_text(
    text: str,
    max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH,
    suffix: Optional[str] = None,
    lang: str = DEFAULT_LANGUAGE,
) -> str:
    """
    Cut `text` to at most `max_length` characters, the last ones being `suffix`.

    Without `suffix`, a newline and the translated "(truncated)" marker for `lang` are used.
    """
    if len(text) <= max_length:
        return text
    if suffix is None:
        suffix = "\n" + t("truncated_suffix", lang)
    cut_len = max(0, max_length - len(suffix))
    return text[:cut_len] + suffix
