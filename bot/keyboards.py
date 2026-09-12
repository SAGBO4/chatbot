from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_resolution_keyboard(ticket_id: int = 0) -> InlineKeyboardMarkup:
    """Inline keyboard for user resolution confirmation."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ OUI", callback_data=f"resolve:yes:{ticket_id}"),
            InlineKeyboardButton(text="❌ NON", callback_data=f"resolve:no:{ticket_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
