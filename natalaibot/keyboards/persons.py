from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from natalaibot.models import PersonRead


def persons_keyboard(
    persons: list[PersonRead],
    page: int,
    total: int,
    page_size: int = 5,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=person.person_name or "Без имени", callback_data=f"persons:open:{person.person_id}:{page}")]
        for person in persons[:page_size]
    ]

    pagination = _pagination_row(prefix="persons:page", page=page, total=total, page_size=page_size)
    if pagination:
        rows.append(pagination)

    rows.append([InlineKeyboardButton(text="назад", callback_data="main:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def person_detail_keyboard(person_id: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="удалить персону", callback_data=f"persons:delete:{person_id}:{page}")],
            [InlineKeyboardButton(text="назад", callback_data=f"persons:page:{page}")],
        ]
    )


def _pagination_row(prefix: str, page: int, total: int, page_size: int) -> list[InlineKeyboardButton]:
    buttons: list[InlineKeyboardButton] = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="<-", callback_data=f"{prefix}:{page - 1}"))
    if (page + 1) * page_size < total:
        buttons.append(InlineKeyboardButton(text="->", callback_data=f"{prefix}:{page + 1}"))
    return buttons
