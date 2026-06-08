from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from natalaibot.config import Settings
from natalaibot.keyboards.generation import generation_menu_keyboard
from natalaibot.keyboards.start import main_keyboard

router = Router()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    await message.answer("Выберите раздел:", reply_markup=main_keyboard(settings.offer_url))


@router.callback_query(F.data == "main:menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    await callback.message.edit_text("Выберите раздел:", reply_markup=main_keyboard(settings.offer_url))
    await callback.answer()


@router.callback_query(F.data == "main:generation")
async def show_generation_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Генерации:", reply_markup=generation_menu_keyboard())
    await callback.answer()
