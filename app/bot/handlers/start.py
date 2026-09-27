import logging
from html import escape

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.bot.keyboards import build_employee_menu_keyboard, build_share_phone_keyboard
from app.repositories import UserRepository
from app.services.onboarding import (
    EmployeeOnboardingService,
    OnboardingError,
    OnboardingErrorCode,
    account_access_message,
)


class OnboardingStates(StatesGroup):
    WAITING_FOR_NAME = State()
    WAITING_FOR_PHONE = State()


router = Router(name=__name__)
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.from_user is None:
        await message.answer("Foydalanuvchi ma'lumotlari topilmadi.")
        return

    await state.clear()

    service = EmployeeOnboardingService(UserRepository(session))
    user = await service.get_registered_user(message.from_user.id)

    if user is not None:
        access_message = account_access_message(user)
        if access_message:
            await message.answer(access_message)
            return
        await message.answer(
            build_employee_menu_text(user.full_name),
            reply_markup=build_employee_menu_keyboard(),
        )
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
    if user.approval_status == "PENDING":
        await session.commit()
        await notify_owners_of_registration(message, user)
        await message.answer(
            "✅ Arizangiz rahbarlarga yuborildi. Hisobingiz tasdiqlangach, botdan "
            "foydalanishingiz mumkin."
        )
        return

    access_message = account_access_message(user)
    if access_message:
        await message.answer(access_message)
        return

    await message.answer(
        build_employee_menu_text(user.full_name),
        reply_markup=build_employee_menu_keyboard(),
    )


async def notify_owners_of_registration(message: Message, user) -> None:
    settings = get_settings()
    if message.bot is None:
        logger.error("cannot_notify_owners_without_bot_instance")
        return

    username = message.from_user.username if message.from_user else None
    username_line = f"\n🔗 <b>Username:</b> @{escape(username)}" if username else ""
    request_text = (
        "🆕 <b>YANGI XODIM RO'YXATDAN O'TMOQCHI</b>\n\n"
        f"👤 <b>Ism:</b> {escape(user.full_name)}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.telegram_id}</code>"
        f"{username_line}\n\nUshbu xodimga botdan foydalanishga ruxsat berasizmi?"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"registration_approve:{user.id}",
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"registration_reject:{user.id}",
                ),
            ]
        ]
    )
    destinations = (
        [settings.boss_channel_id]
        if settings.boss_channel_id
        else list(settings.owner_ids)
    )
    for destination in destinations:
        try:
            await message.bot.send_message(
                chat_id=destination,
                text=request_text,
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception(
                "failed_to_send_registration_approval_request",
                extra={"destination_id": str(destination), "telegram_id": user.telegram_id},
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
