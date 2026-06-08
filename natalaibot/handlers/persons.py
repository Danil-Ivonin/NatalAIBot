from aiogram import F, Router
from aiogram.types import CallbackQuery

from natalaibot.http.users_client import UsersAPIError, UsersClient
from natalaibot.keyboards.persons import person_detail_keyboard, persons_keyboard
from natalaibot.keyboards.start import main_keyboard
from natalaibot.models import PersonRead

router = Router()
PAGE_SIZE = 5


@router.callback_query(F.data == "main:persons")
@router.callback_query(F.data.startswith("persons:page:"))
async def show_persons(callback: CallbackQuery, users_client: UsersClient) -> None:
    page = _extract_page(callback.data or "persons:page:0")
    await _edit_persons_page(callback, users_client=users_client, page=page)
    await callback.answer()


@router.callback_query(F.data.startswith("persons:open:"))
async def open_person(callback: CallbackQuery, users_client: UsersClient) -> None:
    person_id, page = _extract_person_and_page(callback.data or "")
    try:
        person = await users_client.get_person(callback.from_user.id, person_id)
    except UsersAPIError:
        await callback.message.edit_text(
            "Сервис персон временно недоступен. Попробуйте позже.",
            reply_markup=main_keyboard("https://example.com/offer.pdf"),
        )
        await callback.answer()
        return

    await callback.message.edit_text(format_person(person), reply_markup=person_detail_keyboard(person.person_id, page))
    await callback.answer()


@router.callback_query(F.data.startswith("persons:delete:"))
async def delete_person(callback: CallbackQuery, users_client: UsersClient) -> None:
    person_id, page = _extract_person_and_page(callback.data or "", prefix="persons:delete:")
    try:
        await users_client.delete_person(callback.from_user.id, person_id)
    except UsersAPIError:
        await callback.message.edit_text(
            "Сервис персон временно недоступен. Попробуйте позже.",
            reply_markup=main_keyboard("https://example.com/offer.pdf"),
        )
        await callback.answer()
        return

    await callback.message.edit_text("Персона удалена.", reply_markup=persons_keyboard([], page=page, total=0))
    await callback.answer()


def format_person(person: PersonRead) -> str:
    gender = {"female": "женский", "male": "мужской", None: "не указан"}[person.gender]
    return (
        f"Имя: {person.person_name or 'не указано'}\n"
        f"Пол: {gender}\n"
        f"Дата рождения: {person.birth_date} {person.birth_time}\n"
        f"Место рождения: {person.birth_place.addr}"
    )


async def _edit_persons_page(callback: CallbackQuery, users_client: UsersClient, page: int) -> None:
    try:
        persons_page = await users_client.list_persons(
            telegram_id=callback.from_user.id,
            limit=PAGE_SIZE,
            offset=page * PAGE_SIZE,
        )
    except UsersAPIError:
        await callback.message.edit_text(
            "Сервис персон временно недоступен. Попробуйте позже.",
            reply_markup=main_keyboard("https://example.com/offer.pdf"),
        )
        return

    await callback.message.edit_text(
        "Ваши персоны:",
        reply_markup=persons_keyboard(persons_page.items, page=page, total=persons_page.total, page_size=PAGE_SIZE),
    )


def _extract_page(data: str) -> int:
    if data == "main:persons":
        return 0
    return max(int(data.rsplit(":", maxsplit=1)[-1]), 0)


def _extract_person_and_page(data: str, prefix: str = "persons:open:") -> tuple[str, int]:
    payload = data.removeprefix(prefix)
    person_id, page = payload.rsplit(":", maxsplit=1)
    return person_id, max(int(page), 0)
