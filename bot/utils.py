import re

TELEGRAM_MAX_MESSAGE_LENGTH = 4000


def escape_telegram_markdown(text: str) -> str:
    """Escapes legacy Telegram Markdown metacharacters in untrusted text."""
    return re.sub(r"([_*`\[])", r"\\\1", text)


def truncate_telegram_text(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH, suffix: str = "\n...(tronqué)") -> str:
    """Truncates text to fit within Telegram message length limits."""
    if len(text) <= max_length:
        return text
    cut_len = max(0, max_length - len(suffix))
    return text[:cut_len] + suffix
