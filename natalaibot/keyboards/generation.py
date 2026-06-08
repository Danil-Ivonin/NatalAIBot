from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from natalaibot.models import Character, GenerationLinkRead, PersonRead


def generation_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Запустить новую генерацию", callback_data="generation:new")],
            [InlineKeyboardButton(text="Список генераций", callback_data="generation:list:0")],
            [InlineKeyboardButton(text="назад", callback_data="main:menu")],
        ]
    )


def new_generation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сделать разбор натальной карты", callback_data="generation:natal")],
            [InlineKeyboardButton(text="Проверить совместимость", callback_data="generation:compatibility")],
            [InlineKeyboardButton(text="назад", callback_data="generation:menu")],
        ]
    )


def person_selection_keyboard(
    persons: list[PersonRead],
    page: int,
    total: int,
    page_size: int = 5,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=person.person_name or "Без имени",
                callback_data=f"generation:person:{person.person_id}:{page}",
            )
        ]
        for person in persons[:page_size]
    ]

    pagination = _pagination_row(prefix="generation:person_page", page=page, total=total, page_size=page_size)
    if pagination:
        rows.append(pagination)

    rows.append([InlineKeyboardButton(text="добавить нового человека", callback_data="generation:person:add")])
    rows.append([InlineKeyboardButton(text="назад", callback_data="generation:new")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def character_keyboard(characters: list[Character]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=character.name, callback_data=f"generation:character:{character.id}")]
            for character in characters
        ]
    )


def generation_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="оплатить", callback_data="generation:confirm:pay")],
            [InlineKeyboardButton(text="назад", callback_data="generation:confirm:back")],
        ]
    )


def generation_history_keyboard(
    links: list[GenerationLinkRead],
    page: int,
    total: int,
    page_size: int = 5,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=_generation_link_text(link),
                callback_data=f"generation:history:open:{link.generation_id}:{page}",
            )
        ]
        for link in links[:page_size]
    ]

    pagination = _pagination_row(prefix="generation:list", page=page, total=total, page_size=page_size)
    if pagination:
        rows.append(pagination)

    rows.append([InlineKeyboardButton(text="назад", callback_data="generation:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_generation_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="назад", callback_data="generation:menu")]]
    )


def _pagination_row(prefix: str, page: int, total: int, page_size: int) -> list[InlineKeyboardButton]:
    buttons: list[InlineKeyboardButton] = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="<-", callback_data=f"{prefix}:{page - 1}"))
    if (page + 1) * page_size < total:
        buttons.append(InlineKeyboardButton(text="->", callback_data=f"{prefix}:{page + 1}"))
    return buttons


def _generation_link_text(link: GenerationLinkRead) -> str:
    if link.created_at:
        return f"{link.created_at} · {link.generation_id}"
    return link.generation_id
