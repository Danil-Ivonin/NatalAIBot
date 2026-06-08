import asyncio
from datetime import datetime
from urllib.parse import urlparse

import httpx
from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from natalaibot.config import Settings
from natalaibot.http.backend_client import BackendAPIError, BackendClient
from natalaibot.http.users_client import UsersAPIError, UsersClient
from natalaibot.infra.formatting import format_report_sections, split_telegram_message
from natalaibot.infra.geo_extractor import GeocodingError, geocode_address
from natalaibot.infra.payment import PaymentService
from natalaibot.keyboards.generation import (
    back_to_generation_menu_keyboard,
    character_keyboard,
    generation_confirm_keyboard,
    generation_history_keyboard,
    generation_menu_keyboard,
    new_generation_keyboard,
    person_selection_keyboard,
)
from natalaibot.models import (
    Character,
    ChartImage,
    GenerationCreate,
    GenerationRead,
    PersonCreate,
    PersonRead,
)

router = Router()
PAGE_SIZE = 5


class NatalForm(StatesGroup):
    person_name = State()
    gender = State()
    birth_date = State()
    birth_time = State()
    birth_place = State()
    confirm_data = State()
    persona = State()
    payment = State()


@router.callback_query(F.data == "generation:menu")
async def show_generation_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Генерации:", reply_markup=generation_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "generation:new")
async def show_new_generation_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Запустить новую генерацию:", reply_markup=new_generation_keyboard())
    await callback.answer()


@router.callback_query(F.data == "generation:compatibility")
async def show_compatibility_placeholder(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Раздел проверки совместимости скоро появится.",
        reply_markup=back_to_generation_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "generation:natal")
@router.callback_query(F.data.startswith("generation:person_page:"))
async def show_person_selection(callback: CallbackQuery, users_client: UsersClient) -> None:
    page = _extract_page(callback.data or "generation:natal")
    try:
        persons_page = await users_client.list_persons(
            telegram_id=callback.from_user.id,
            limit=PAGE_SIZE,
            offset=page * PAGE_SIZE,
        )
    except UsersAPIError:
        await callback.message.edit_text(
            "Сервис персон временно недоступен. Попробуйте позже.",
            reply_markup=back_to_generation_menu_keyboard(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "Выберите персону, для которой нужно сделать разбор",
        reply_markup=person_selection_keyboard(persons_page.items, page=page, total=persons_page.total),
    )
    await callback.answer()


@router.callback_query(lambda callback: callback.data and callback.data.startswith("generation:person:") and callback.data != "generation:person:add")
async def select_existing_person(callback: CallbackQuery, state: FSMContext, users_client: UsersClient, backend_client: BackendClient) -> None:
    person_id = (callback.data or "").split(":")[2]
    try:
        person = await users_client.get_person(callback.from_user.id, person_id)
    except UsersAPIError:
        await callback.message.edit_text(
            "Сервис персон временно недоступен. Попробуйте позже.",
            reply_markup=back_to_generation_menu_keyboard(),
        )
        await callback.answer()
        return

    await state.update_data(selected_person=person.model_dump(mode="python"))
    await _ask_character(callback.message, state, backend_client)
    await callback.answer()


@router.callback_query(F.data == "generation:person:add")
async def add_new_person(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NatalForm.person_name)
    await callback.message.edit_text("Как зовут человека?")
    await callback.answer()


@router.message(NatalForm.person_name)
async def collect_name(message: Message, state: FSMContext) -> None:
    person_name = message.text.strip() if message.text else None
    await state.update_data(person_name=person_name or None)
    await state.set_state(NatalForm.gender)
    await message.answer(
        "Выбери пол:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Женский"), KeyboardButton(text="Мужской")],
                [KeyboardButton(text="Не указывать")],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(NatalForm.gender)
async def collect_gender(message: Message, state: FSMContext) -> None:
    gender = _parse_gender(message.text or "")
    if gender == "invalid":
        await message.answer("Выбери вариант с клавиатуры: Женский, Мужской или Не указывать.")
        return

    await state.update_data(gender=gender)
    await state.set_state(NatalForm.birth_date)
    await message.answer("Дата рождения в формате ДД.ММ.ГГГГ:", reply_markup=ReplyKeyboardRemove())


@router.message(NatalForm.birth_date)
async def collect_birth_date(message: Message, state: FSMContext) -> None:
    try:
        birth_date = _parse_date(message.text or "")
    except ValueError:
        await message.answer("Не получилось разобрать дату. Пример: 02.01.1990")
        return

    await state.update_data(birth_date=birth_date)
    await state.set_state(NatalForm.birth_time)
    await message.answer("Время рождения в формате ЧЧ:ММ. Если известно точно, отлично! Если нет, укажи примерное.")


@router.message(NatalForm.birth_time)
async def collect_birth_time(message: Message, state: FSMContext) -> None:
    try:
        birth_time = _parse_time(message.text or "")
    except ValueError:
        await message.answer("Не получилось разобрать время. Пример: 03:04")
        return

    await state.update_data(birth_time=birth_time)
    await state.set_state(NatalForm.birth_place)
    await message.answer("Место рождения одной строкой.")


@router.message(NatalForm.birth_place)
async def collect_birth_place(message: Message, state: FSMContext, settings: Settings) -> None:
    try:
        birth_place = await geocode_address(
            message.text or "",
            settings.locationiq_url,
            settings.locationiq_token,
            language="ru",
        )
    except (GeocodingError, ValueError):
        await message.answer("Не получилось разобрать место рождения.")
        return

    await state.update_data(birth_place=birth_place)
    await state.set_state(NatalForm.confirm_data)
    data = await state.get_data()
    await message.answer(
        _format_person_confirmation(data),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Верно"), KeyboardButton(text="Ввести заново")]],
            resize_keyboard=True,
        ),
    )


@router.message(NatalForm.confirm_data)
async def collect_confirm_data(
    message: Message,
    state: FSMContext,
    users_client: UsersClient,
    backend_client: BackendClient,
    telegram_id: int | None = None,
) -> None:
    if not _parse_confirm(message.text or ""):
        await state.clear()
        await message.answer("Ок, остановил сценарий.", reply_markup=ReplyKeyboardRemove())
        return

    data = await state.get_data()
    try:
        person = await users_client.create_person(
            telegram_id=telegram_id or message.from_user.id,
            payload=PersonCreate(
                person_name=data.get("person_name"),
                gender=data.get("gender"),
                birth_date=data["birth_date"],
                birth_time=data["birth_time"],
                birth_place=data["birth_place"],
            ),
        )
    except UsersAPIError:
        await message.answer(
            "Не удалось сохранить персону. Попробуйте позже.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.clear()
        return

    await state.update_data(selected_person=person.model_dump(mode="python"))
    await _ask_character(message, state, backend_client)


@router.callback_query(NatalForm.persona, F.data.startswith("generation:character:"))
async def collect_character(callback: CallbackQuery, state: FSMContext, backend_client: BackendClient) -> None:
    character_id = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    characters = await backend_client.list_active_characters()
    character = next((item for item in characters if item.id == character_id), None)
    if character is None:
        await callback.message.edit_text("Персонаж недоступен. Выберите действие заново.", reply_markup=back_to_generation_menu_keyboard())
        await callback.answer()
        return

    await state.update_data(selected_character=character.model_dump(mode="python"))
    await state.set_state(NatalForm.payment)
    data = await state.get_data()
    person = PersonRead.model_validate(data["selected_person"])
    await callback.message.edit_text(
        _format_generation_confirmation(person, character),
        reply_markup=generation_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(NatalForm.payment, F.data == "generation:confirm:back")
async def back_from_confirmation(callback: CallbackQuery, state: FSMContext, backend_client: BackendClient) -> None:
    await _ask_character(callback.message, state, backend_client)
    await callback.answer()


@router.callback_query(NatalForm.payment, F.data == "generation:confirm:pay")
async def request_payment(
    callback: CallbackQuery,
    state: FSMContext,
    payment_service: PaymentService,
    backend_client: BackendClient,
    users_client: UsersClient,
    settings: Settings,
) -> None:
    payment_result = await payment_service.request_payment(callback.from_user.id)
    await state.update_data(payment_id=payment_result.payment_id)
    await run_generation(
        callback,
        state,
        backend_client=backend_client,
        users_client=users_client,
        settings=settings,
    )


async def run_generation(
    callback: CallbackQuery,
    state: FSMContext,
    backend_client: BackendClient,
    users_client: UsersClient,
    settings: Settings,
) -> None:
    data = await state.get_data()
    person = PersonRead.model_validate(data["selected_person"])
    character = Character.model_validate(data["selected_character"])
    payload = GenerationCreate(
        person_name=person.person_name,
        gender=person.gender,
        birth_date=person.birth_date,
        birth_time=person.birth_time,
        birth_place=person.birth_place,
        persona_id=character.id,
    )

    await callback.message.edit_text("Отлично!\nЗапускаю генерацию. Это может занять немного времени.")
    await callback.answer()

    try:
        created = await backend_client.create_generation(payload)
    except BackendAPIError as exc:
        await callback.message.answer(f"Backend вернул ошибку: {exc}")
        return

    try:
        await users_client.create_generation_link(callback.from_user.id, created.generation_id)
    except Exception:
        await callback.message.answer("Генерация запущена, но может не появиться в истории.")

    try:
        generation = await _wait_for_generation(
            backend_client=backend_client,
            generation_id=created.generation_id,
            attempts=settings.generation_poll_attempts,
            interval_seconds=settings.generation_poll_interval_seconds,
        )
    except BackendAPIError as exc:
        await callback.message.answer(f"Backend вернул ошибку: {exc}")
        return

    await _send_generation_result(callback.message, generation)
    await state.clear()


@router.callback_query(F.data.startswith("generation:list:"))
async def show_generation_history(callback: CallbackQuery, users_client: UsersClient) -> None:
    page = _extract_page(callback.data or "generation:list:0")
    try:
        links_page = await users_client.list_generation_links(
            telegram_id=callback.from_user.id,
            limit=PAGE_SIZE,
            offset=page * PAGE_SIZE,
        )
    except UsersAPIError:
        await callback.message.edit_text(
            "Сервис генераций временно недоступен. Попробуйте позже.",
            reply_markup=back_to_generation_menu_keyboard(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "Ваши генерации:",
        reply_markup=generation_history_keyboard(links_page.items, page=page, total=links_page.total),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("generation:history:open:"))
async def open_generation_history_item(callback: CallbackQuery, backend_client: BackendClient) -> None:
    generation_id = (callback.data or "").split(":")[3]
    try:
        generation = await backend_client.get_generation(generation_id)
    except BackendAPIError as exc:
        await callback.message.answer(f"Backend вернул ошибку: {exc}")
        await callback.answer()
        return

    await _send_generation_result(callback.message, generation)
    await callback.answer()


async def _ask_character(message: Message, state: FSMContext, backend_client: BackendClient) -> None:
    try:
        characters = await backend_client.list_active_characters()
    except BackendAPIError as exc:
        await message.answer(f"Не смог получить список персонажей от backend: {exc}", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    if not characters:
        await message.answer("Сервис временно недоступен. Попробуйте позже.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    await state.set_state(NatalForm.persona)
    await message.answer("Выберите персонажа, в чьём стиле будет выполнен разбор", reply_markup=character_keyboard(characters))


async def _send_generation_result(message: Message, generation: GenerationRead) -> None:
    if generation.status == "failed":
        await message.answer(f"Генерация завершилась ошибкой: {generation.error_message or 'без деталей'}")
        return

    if generation.result_text is None:
        await message.answer("Генерация еще не завершилась. Проверьте список генераций позже.")
        return

    if generation.chart_image:
        try:
            await _send_chart_image(message, generation.chart_image)
        except (TelegramAPIError, httpx.HTTPError, ValueError):
            pass

    for section in format_report_sections(generation.result_text):
        for chunk in split_telegram_message(section):
            await message.answer(chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=False)


async def _wait_for_generation(
    backend_client: BackendClient,
    generation_id: str,
    attempts: int,
    interval_seconds: float,
) -> GenerationRead:
    for _ in range(attempts):
        generation = await backend_client.get_generation(generation_id)
        if generation.status in {"completed", "failed"}:
            return generation
        await asyncio.sleep(interval_seconds)

    return await backend_client.get_generation(generation_id)


async def _send_chart_image(message: Message, chart_image: ChartImage) -> None:
    photo = BufferedInputFile(
        await _download_url(chart_image.url),
        filename=_filename_from_url(chart_image.url, default="natal-chart.png"),
    )
    await message.answer_photo(photo)


async def _download_url(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, trust_env=False) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _filename_from_url(url: str, default: str) -> str:
    filename = urlparse(url).path.rsplit("/", maxsplit=1)[-1]
    return filename or default


def _format_person_confirmation(data: dict) -> str:
    birth_place = data.get("birth_place")
    return (
        "Подтвердите правильность данных:\n"
        f"Имя: {data.get('person_name') or 'не указано'}\n"
        f"Дата рождения: {data.get('birth_date')} {data.get('birth_time')}\n"
        f"Место рождения: {birth_place.addr}"
    )


def _format_generation_confirmation(person: PersonRead, character: Character) -> str:
    description = f"\nОписание персонажа: {character.description}" if character.description else ""
    return (
        "Подтвердите правильность данных:\n"
        f"{_format_person(person)}\n\n"
        f"Персонаж: {character.name}{description}"
    )


def _format_person(person: PersonRead) -> str:
    return (
        f"Имя: {person.person_name or 'не указано'}\n"
        f"Дата рождения: {person.birth_date} {person.birth_time}\n"
        f"Место рождения: {person.birth_place.addr}"
    )


def _extract_page(data: str) -> int:
    if data == "generation:natal":
        return 0
    return max(int(data.rsplit(":", maxsplit=1)[-1]), 0)


def _parse_gender(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized == "женский":
        return "female"
    if normalized == "мужской":
        return "male"
    if normalized == "не указывать":
        return None
    return "invalid"


def _parse_confirm(value: str) -> bool:
    return value.strip().lower() == "верно"


def _parse_date(value: str) -> str:
    return datetime.strptime(value.strip(), "%d.%m.%Y").date().isoformat()


def _parse_time(value: str) -> str:
    return datetime.strptime(value.strip(), "%H:%M").time().isoformat()
