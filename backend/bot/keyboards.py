from typing import Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from bot.i18n import DEFAULT_LANGUAGE, t


def get_resolution_keyboard(ticket_id: int = 0, lang: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Inline YES / NO keyboard asking whether the answer solved the problem, in `lang`."""
    buttons = [
        [
            InlineKeyboardButton(text=t("button_yes", lang), callback_data=f"resolve:yes:{ticket_id}"),
            InlineKeyboardButton(text=t("button_no", lang), callback_data=f"resolve:no:{ticket_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_community_resolution_keyboard(lang: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """
    Inline keyboard for the community-group Q&A resolution confirmation.

    Uses a distinct callback_data prefix ("cresolve:") from the private-DM
    keyboard so the two flows never collide when routed through the same
    Dispatcher (see bot/handlers/community_handlers.py).
    """
    buttons = [
        [
            InlineKeyboardButton(text=t("button_yes", lang), callback_data="cresolve:yes"),
            InlineKeyboardButton(text=t("button_no", lang), callback_data="cresolve:no"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_webapp_keyboard(url: str, text: Optional[str] = None, lang: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Inline keyboard with a button that opens the Mini App; `text` overrides the default label."""
    buttons = [
        [
            InlineKeyboardButton(text=text or t("button_webapp", lang), web_app=WebAppInfo(url=url)),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
