import re


def escape_telegram_markdown(text: str) -> str:
    """Escapes legacy Telegram Markdown metacharacters in untrusted text."""
    return re.sub(r"([_*`\[])", r"\\\1", text)
