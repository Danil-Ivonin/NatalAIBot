from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard(offer_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Персоны", callback_data="main:persons")],
            [InlineKeyboardButton(text="Генерации", callback_data="main:generation")],
            [InlineKeyboardButton(text="Информация", url=offer_url)],
        ]
    )
