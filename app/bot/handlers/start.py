from html import escape

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import build_employee_menu_keyboard, build_share_phone_keyboard
from app.repositories import UserRepository
from app.services.onboarding import (
    EmployeeOnboardingService,
    OnboardingError,
    OnboardingErrorCode,
)


class OnboardingStates(StatesGroup):
    WAITING_FOR_NAME = State()
    WAITING_FOR_PHONE = State()


router = Router(name=__name__)


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.from_user is None:
        await message.answer("Foydalanuvchi ma'lumotlari topilmadi.")
        return

    await state.clear()

    service = EmployeeOnboardingService(UserRepository(session))
    user = await service.get_registered_user(message.from_user.id)

    if user is not None and user.is_active:
        await message.answer(
            build_employee_menu_text(user.full_name),
            reply_markup=build_employee_menu_keyboard(),
        )
        return

    if user is not None and not user.is_active:
        await message.answer("Hisobingiz faol emas. Iltimos, menejerga murojaat qiling.")
        return

    await message.answer(
        "Assalomu alaykum!\n\n"
        "Ro'yxatdan o'tish uchun ismingizni kiriting."
    )
    await state.set_state(OnboardingStates.WAITING_FOR_NAME)


@router.message(OnboardingStates.WAITING_FOR_NAME)
async def handle_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.from_user is None or message.text is None:
        await message.answer("Iltimos, ismingizni matn shaklida kiriting.")
        return

    full_name = message.text.strip()
    if len(full_name) < 2:
        await message.answer("Ism juda qisqa. Iltimos, to'liq ismingizni kiriting.")
        return

    service = EmployeeOnboardingService(UserRepository(session))
    user = await service.register_new_user(
        telegram_id=message.from_user.id,
        full_name=full_name,
    )

    await state.clear()
    await message.answer(
        build_employee_menu_text(user.full_name),
        reply_markup=build_employee_menu_keyboard(),
    )


def build_employee_menu_text(name: str) -> str:
    safe_name = escape(name)
    return (
        "🍎 MEVACHI\n\n"
        f"Assalomu alaykum, {safe_name}!\n\n"
        "🟢 KELDIM\n"
        "🔴 KETDIM\n"
        "📋 MENING DAVOMATIM"
    )


def build_onboarding_error_message(code: OnboardingErrorCode) -> str:
    messages = {
        OnboardingErrorCode.INVALID_PHONE: (
            "Telefon raqam formati noto'g'ri. Iltimos, pastdagi tugma orqali qayta yuboring."
        ),
        OnboardingErrorCode.PHONE_ALREADY_EXISTS: (
            "Bu telefon raqam allaqachon ro'yxatdan o'tgan. Iltimos, boshqa raqam yoki administratorga murojaat qiling."
        ),
    }
    return messages[code]
