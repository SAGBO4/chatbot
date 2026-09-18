from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo


def get_resolution_keyboard(ticket_id: int = 0) -> InlineKeyboardMarkup:
    """Inline keyboard for user resolution confirmation."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ OUI", callback_data=f"resolve:yes:{ticket_id}"),
            InlineKeyboardButton(text="❌ NON", callback_data=f"resolve:no:{ticket_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_community_resolution_keyboard() -> InlineKeyboardMarkup:
    """
    Inline keyboard for the community-group Q&A resolution confirmation.

    Uses a distinct callback_data prefix ("cresolve:") from the private-DM
    keyboard so the two flows never collide when routed through the same
    Dispatcher (see bot/handlers/community_handlers.py).
    """
    buttons = [
        [
            InlineKeyboardButton(text="✅ OUI", callback_data="cresolve:yes"),
            InlineKeyboardButton(text="❌ NON", callback_data="cresolve:no"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_webapp_keyboard(url: str, text: str = "📱 Centre d'Assistance Stack") -> InlineKeyboardMarkup:
    """Inline keyboard with a WebApp button for opening the Next.js Mini App."""
    buttons = [
        [
            InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url)),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
