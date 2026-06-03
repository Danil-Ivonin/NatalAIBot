import asyncio
from datetime import datetime
from urllib.parse import urlparse

import httpx
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    BufferedInputFile,
)

from natalaibot.backend_client import BackendAPIError, BackendClient
from natalaibot.config import Settings
from natalaibot.formatting import format_report_sections, split_telegram_message
from natalaibot.geo_extractor import GeocodingError, geocode_address
from natalaibot.models import ChartImage, GenerationCreate, Persona
from natalaibot.payment import PaymentService

router = Router()


class NatalForm(StatesGroup):
    person_name = State()
    gender = State()
    birth_date = State()
    birth_time = State()
    birth_place = State()
    confirm_data = State()
    persona = State()
    payment = State()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(NatalForm.person_name)
    await message.answer(
        "Привет. Соберу данные рождения, предложу персонажа и отправлю запрос на генерацию натальной карты.\n\n"
        "Как тебя зовут?",
        reply_markup=ReplyKeyboardRemove(),
    )

@router.message(Command("image"))
async def image(message: Message, backend_client: BackendClient, settings: Settings) -> None:

    generation = await _wait_for_generation(
        backend_client=backend_client,
        generation_id="113b7345-529e-40ae-a113-91986e8ed212",
        attempts=settings.generation_poll_attempts,
        interval_seconds=settings.generation_poll_interval_seconds,
    )


    if generation.chart_image:
        try:
            await _send_chart_image(message, generation.chart_image)
        except (TelegramAPIError, httpx.HTTPError):
            await message.answer("Не смог отправить изображение натальной карты.")


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Ок, остановил сценарий. Чтобы начать заново, нажми /start.", reply_markup=ReplyKeyboardRemove()
    )


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
async def collect_birth_place(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    try:
        birth_place = await geocode_address(
            message.text or "", settings.nomina_url, settings.nomina_base_agent, language="ru"
        )
        await state.update_data(birth_place=birth_place)
    except (GeocodingError, ValueError):
        await message.answer("Не получилось разобрать место рождения.")
        return


    await state.set_state(NatalForm.confirm_data)
    data = await state.get_data()
    msg = f"""Подтвердите, что данные введены правильно:
    Имя: {data.get("person_name")}
    Дата рождения: {data.get("birth_date")} {data.get("birth_time")}
    Место рождения: {data.get("birth_place").addr} {data.get("birth_place").timezone} 
    """
    await message.answer(
        msg,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Верно"), KeyboardButton(text="Ввести заново")]
            ],
            resize_keyboard=True,
        ),
    )

@router.message(NatalForm.confirm_data)
async def collect_confirm_data(
    message: Message, state: FSMContext, backend_client: BackendClient
) -> None:
    if not _parse_confirm(message.text or ""):
        await state.clear()
        await message.answer(
            "Ок, остановил сценарий. Чтобы начать заново, нажми /start.", reply_markup=ReplyKeyboardRemove()
        )
        return

    try:
        personas = await backend_client.list_active_personas()
    except BackendAPIError as exc:
        await message.answer(f"Не смог получить список персонажей от backend: {exc}", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    if not personas:
        await message.answer(
            "На данный момент сервис недоступен или ведутся технические работы. Пожалуйста, попробуйте позже", reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
        return

    await state.set_state(NatalForm.persona)

    await message.answer("Отлично!", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        "Выбери персонажа, от чьего имени будет разобрана натальная карта:",
        reply_markup=_persona_keyboard(personas),
    )

@router.callback_query(NatalForm.persona, F.data.startswith("persona:"))
async def collect_persona(callback: CallbackQuery, state: FSMContext, payment_service: PaymentService) -> None:
    persona_id = (callback.data or "").split(":", maxsplit=1)[1]
    await state.update_data(persona_id=persona_id)
    await state.set_state(NatalForm.payment)

    payment_result = await payment_service.request_payment(callback.from_user.id)
    await state.update_data(payment_id=payment_result.payment_id)

    await callback.message.edit_text(
        "Оплатите генерацию, чтобы продолжить",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Оплатить", callback_data="payment:paid")]]
        ),
    )
    await callback.answer()


@router.callback_query(NatalForm.payment, F.data == "payment:paid")
async def run_generation(
    callback: CallbackQuery, state: FSMContext, backend_client: BackendClient, settings: Settings
) -> None:
    data = await state.get_data()
    payload = GenerationCreate(
        person_name=data.get("person_name"),
        gender=data.get("gender"),
        birth_date=data["birth_date"],
        birth_time=data["birth_time"],
        birth_place=data["birth_place"],
        persona_id=data["persona_id"],
    )

    await callback.message.edit_text("Отлично!\nЗапускаю генерацию. Это может занять немного времени.")
    await callback.answer()

    try:
        created = await backend_client.create_generation(payload)
        generation = await _wait_for_generation(
            backend_client=backend_client,
            generation_id=created.generation_id,
            attempts=settings.generation_poll_attempts,
            interval_seconds=settings.generation_poll_interval_seconds,
        )
    except BackendAPIError as exc:
        await callback.message.answer(f"Backend вернул ошибку: {exc}")
        return

    if generation.status == "failed":
        await callback.message.answer(f"Генерация завершилась ошибкой: {generation.error_message or 'без деталей'}")
        return

    if generation.result_text is None:
        await callback.message.answer("Генерация еще не завершилась. Попробуй запросить результат позже.")
        return

    if generation.chart_image:
        try:
            await _send_chart_image(callback.message, generation.chart_image)
        except (TelegramAPIError, httpx.HTTPError):
            pass

    for section in format_report_sections(generation.result_text):
        for chunk in split_telegram_message(section):
            await callback.message.answer(chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=False)

    await state.clear()


def create_dispatcher(settings: Settings, backend_client: BackendClient, payment_service: PaymentService) -> Dispatcher:
    dispatcher = Dispatcher(
        settings=settings,
        backend_client=backend_client,
        payment_service=payment_service,
    )
    dispatcher.include_router(router)
    return dispatcher


async def run_bot(settings: Settings) -> None:
    print("starting bot...")
    bot = Bot(token=settings.bot_token)
    backend_client = BackendClient(base_url=settings.backend_base_url)
    dispatcher = create_dispatcher(
        settings=settings,
        backend_client=backend_client,
        payment_service=PaymentService(),
    )

    try:
        await dispatcher.start_polling(bot)
    finally:
        await backend_client.aclose()
        await bot.session.close()


async def _wait_for_generation(
    backend_client: BackendClient,
    generation_id: str,
    attempts: int,
    interval_seconds: float,
):
    for _ in range(attempts):
        generation = await backend_client.get_generation(generation_id)
        if generation.status in {"completed", "failed"}:
            return generation
        await asyncio.sleep(interval_seconds)

    return await backend_client.get_generation(generation_id)


async def _send_chart_image(message: Message, chart_image: ChartImage) -> None:
    if _is_svg_image(chart_image):
        document = BufferedInputFile(
            await _download_url(chart_image.url),
            filename=_filename_from_url(chart_image.url, default="natal-chart.svg"),
        )
        await message.answer_document(document)
        return

    await message.answer_photo(chart_image.url)


async def _download_url(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, trust_env=False) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _is_svg_image(chart_image: ChartImage) -> bool:
    mime_type = chart_image.mime_type.lower().split(";", maxsplit=1)[0].strip()
    path = urlparse(chart_image.url).path.lower()
    return mime_type == "image/svg+xml" or path.endswith(".svg")


def _filename_from_url(url: str, default: str) -> str:
    filename = urlparse(url).path.rsplit("/", maxsplit=1)[-1]
    return filename or default


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
    normalized = value.strip().lower()
    if normalized == "верно":
        return True
    return False

def _parse_date(value: str) -> str:
    return datetime.strptime(value.strip(), "%d.%m.%Y").date().isoformat()


def _parse_time(value: str) -> str:
    return datetime.strptime(value.strip(), "%H:%M").time().isoformat()


def _persona_keyboard(personas: list[Persona]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=persona.name, callback_data=f"persona:{persona.id}")] for persona in personas
        ]
    )
