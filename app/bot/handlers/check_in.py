import logging
from html import escape

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

from app.bot.keyboards import build_branch_selection_keyboard, build_employee_menu_keyboard
from app.models.branch import Branch
from app.repositories import AttendanceRepository, BranchRepository, UserRepository
from app.services.check_in import (
    CheckInError,
    CheckInErrorCode,
    CheckInService,
    CheckOutError,
    CheckOutErrorCode,
)


class CheckInStates(StatesGroup):
    SELECTING_BRANCH = State()
    WAITING_FOR_CHECK_IN_PHOTO = State()
    WAITING_FOR_CHECK_OUT_PHOTO = State()


router = Router(name=__name__)


@router.message(F.text == "🟢 KELDIM")
async def handle_check_in_request(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Handle KELDIM button press - show branch selection."""
    if message.from_user is None:
        await message.answer("Foydalanuvchi ma'lumotlari topilmadi.")
        return

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)

    if user is None:
        await message.answer("Hisobingiz topilmadi. Iltimos, /start buyrug'ini bosing.")
        return

    branch_repo = BranchRepository(session)
    branches = await branch_repo.get_active_branches()

    if not branches:
        await message.answer("Hozircha faol filiallar yo'q. Iltimos, keyinroq urinib ko'ring.")
        return

    await message.answer(
        "Iltimos, filialni tanlang:",
        reply_markup=build_branch_selection_keyboard(branches),
    )
    await state.set_state(CheckInStates.SELECTING_BRANCH)
    await state.update_data(action="check_in")


@router.message(F.text == "🔴 KETDIM")
async def handle_check_out_request(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Ask for a photo before recording check-out."""
    if message.from_user is None:
        await message.answer("Foydalanuvchi ma'lumotlari topilmadi.")
        return

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)

    if user is None:
        await message.answer("Hisobingiz topilmadi. Iltimos, /start buyrug'ini bosing.")
        return

    await message.answer(
        "📸 Iltimos, ishdan chiqayotganingizdagi yangi fotosuratingizni yuboring."
    )
    await state.set_state(CheckInStates.WAITING_FOR_CHECK_OUT_PHOTO)


@router.message(CheckInStates.WAITING_FOR_CHECK_OUT_PHOTO, F.photo)
async def handle_check_out_photo(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if message.from_user is None:
        await message.answer("Foydalanuvchi ma'lumotlari topilmadi.")
        return

    user = await UserRepository(session).get_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer("Hisobingiz topilmadi. Iltimos, /start buyrug'ini bosing.")
        await state.clear()
        return

    try:
        updated_attendance = await CheckInService(AttendanceRepository(session)).process_check_out(user)
    except CheckOutError as exc:
        await message.answer(
            build_check_out_error_message(exc.code),
            reply_markup=build_employee_menu_keyboard(),
        )
        await state.clear()
        return

    updated_attendance.check_out_photo_file_id = message.photo[-1].file_id
    branch_name = updated_attendance.branch.name if updated_attendance.branch else "Filial"
    await state.clear()
    await message.answer(
        build_check_out_success_message(updated_attendance),
        reply_markup=build_employee_menu_keyboard(),
    )

    settings = get_settings()
    if settings.boss_channel_id and message.bot:
        await notify_boss_channel_with_photo(
            message.bot,
            settings.boss_channel_id,
            build_boss_check_out_notification(user.full_name, branch_name, updated_attendance),
            updated_attendance.check_out_photo_file_id,
        )


@router.message(CheckInStates.WAITING_FOR_CHECK_OUT_PHOTO)
async def require_check_out_photo(message: Message) -> None:
    await message.answer("📸 Iltimos, matn emas, fotosurat yuboring.")


@router.message(CheckInStates.SELECTING_BRANCH)
async def handle_branch_selection(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Handle branch selection for check-in."""
    if message.from_user is None or message.text is None:
        await message.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        await state.clear()
        return
    if message.text == "🔴 KETDIM":
        await state.clear()
        await handle_check_out_request(message, state, session)
        return

    branch_repo = BranchRepository(session)
    branches = await branch_repo.get_active_branches()
    
    selected_branch = None
    for branch in branches:
        if branch.name == message.text:
            selected_branch = branch
            break

    if selected_branch is None:
        await message.answer(
            "Iltimos, ro'yxatdan filialni tanlang:",
            reply_markup=build_branch_selection_keyboard(branches),
        )
        return

    user_repo = UserRepository(session)
    attendance_repo = AttendanceRepository(session)
    check_in_service = CheckInService(attendance_repo)

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer("Hisobingiz topilmadi. Iltimos, /start buyrug'ini bosing.")
        await state.clear()
        return

    # Process check-in
    try:
        is_valid, distance_meters = await check_in_service.validate_check_in(
            employee=user,
            branch=selected_branch,
            latitude=float(selected_branch.latitude),
            longitude=float(selected_branch.longitude),
        )
    except CheckInError as exc:
        await message.answer(
            build_check_in_error_message(exc.code),
            reply_markup=build_employee_menu_keyboard(),
        )
        return

    if is_valid and distance_meters is not None:
        await state.update_data(selected_branch_id=selected_branch.id)
        await state.set_state(CheckInStates.WAITING_FOR_CHECK_IN_PHOTO)
        await message.answer(
            f"✅ Filial tanlandi: {escape(selected_branch.name)}\n\n"
            "📸 Endi ishga kelganingizdagi yangi fotosuratingizni yuboring.",
            reply_markup=build_employee_menu_keyboard(),
        )


@router.message(CheckInStates.WAITING_FOR_CHECK_IN_PHOTO, F.photo)
async def handle_check_in_photo(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if message.from_user is None:
        await message.answer("Foydalanuvchi ma'lumotlari topilmadi.")
        return

    state_data = await state.get_data()
    branch_id = state_data.get("selected_branch_id")
    branch = await BranchRepository(session).get_by_id(branch_id) if branch_id else None
    user = await UserRepository(session).get_by_telegram_id(message.from_user.id)
    if user is None or branch is None:
        await message.answer("Sessiya tugadi. Iltimos, 🟢 KELDIM tugmasini qayta bosing.")
        await state.clear()
        return

    check_in_service = CheckInService(AttendanceRepository(session))
    try:
        is_valid, distance_meters = await check_in_service.validate_check_in(
            employee=user,
            branch=branch,
            latitude=float(branch.latitude),
            longitude=float(branch.longitude),
        )
    except CheckInError as exc:
        await message.answer(
            build_check_in_error_message(exc.code),
            reply_markup=build_employee_menu_keyboard(),
        )
        await state.clear()
        return

    attendance = await check_in_service.create_attendance(
        employee=user,
        branch=branch,
        latitude=float(branch.latitude),
        longitude=float(branch.longitude),
        distance_meters=distance_meters or 0.0,
    )
    attendance.check_in_photo_file_id = message.photo[-1].file_id
    await state.clear()
    await message.answer(
        build_check_in_success_message(branch.name),
        reply_markup=build_employee_menu_keyboard(),
    )

    settings = get_settings()
    if settings.boss_channel_id and message.bot:
        await notify_boss_channel_with_photo(
            message.bot,
            settings.boss_channel_id,
            build_boss_check_in_notification(user.full_name, branch.name),
            attendance.check_in_photo_file_id,
        )


@router.message(CheckInStates.WAITING_FOR_CHECK_IN_PHOTO)
async def require_check_in_photo(message: Message) -> None:
    await message.answer("📸 Iltimos, matn emas, fotosurat yuboring.")


def build_check_in_success_message(branch_name: str) -> str:
    """Build success message after successful check-in."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Asia/Tashkent")
    now = datetime.now(tz)
    time_str = now.strftime("%H:%M")

    return (
        "✅ KELDINGIZ\n\n"
        f"🕐 {time_str}\n"
        f"🏪 {branch_name}\n\n"
        "Ishlaringizga omad!"
    )


def build_check_in_error_message(code: CheckInErrorCode) -> str:
    """Build error message for check-in failures."""
    messages = {
        CheckInErrorCode.EMPLOYEE_INACTIVE: (
            "Hisobingiz faol emas. Iltimos, menejerga murojaat qiling."
        ),
        CheckInErrorCode.EMPLOYEE_NO_BRANCH: (
            "Sizga filial biriktirilmagan. Iltimos, menejerga murojaat qiling."
        ),
        CheckInErrorCode.DUPLICATE_CHECK_IN: (
            "Siz allaqachon bugun kelib bo'lgansiz. Davomat belgilangan."
        ),
        CheckInErrorCode.OUTSIDE_RADIUS: (
            "❌ Siz Mevachi filialidan juda uzoqdasiz.\nDavomat belgilanmadi."
        ),
    }
    return messages[code]


def build_check_out_success_message(attendance) -> str:
    """Build success message after successful check-out."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Asia/Tashkent")

    check_in_time = attendance.check_in_at.astimezone(tz).strftime("%H:%M")
    check_out_time = attendance.check_out_at.astimezone(tz).strftime("%H:%M")

    hours, minutes = CheckInService.calculate_work_duration_static(
        attendance.check_in_at, attendance.check_out_at
    )

    return (
        "✅ ISHDAN KETDINGIZ\n\n"
        f"🟢 Keldi: {check_in_time}\n"
        f"🔴 Ketdi: {check_out_time}\n"
        f"⏱️ Ish vaqti: {hours} soat {minutes} daqiqa"
    )


def build_check_out_error_message(code: CheckOutErrorCode) -> str:
    """Build error message for check-out failures."""
    messages = {
        CheckOutErrorCode.NO_ACTIVE_CHECK_IN: (
            "Siz hali ishga kelmadingiz. Avval '🟢 KELDIM' tugmasini bosing."
        ),
        CheckOutErrorCode.ALREADY_CHECKED_OUT: (
            "Siz allaqachon ishdan ketib bo'lgansiz."
        ),
        CheckOutErrorCode.OUTSIDE_RADIUS: (
            "❌ Siz Mevachi filialidan juda uzoqdasiz.\nIshdan ketish belgilanmadi."
        ),
    }
    return messages[code]


logger = logging.getLogger(__name__)


async def notify_boss_channel(bot, channel_id: str | int, text: str) -> None:
    if not bot or not channel_id:
        return
    try:
        await bot.send_message(chat_id=channel_id, text=text)
    except Exception:
        logger.exception("failed_to_send_boss_channel_notification")


async def notify_boss_channel_with_photo(
    bot, channel_id: str | int, caption: str, photo_file_id: str
) -> None:
    if not bot or not channel_id:
        return
    try:
        await bot.send_photo(chat_id=channel_id, photo=photo_file_id, caption=caption)
    except Exception:
        logger.exception("failed_to_send_boss_photo_notification")


def format_duration(hours: int, minutes: int) -> str:
    if hours == 0 and minutes == 0:
        return "0 daqiqa"
    if hours == 0:
        return f"{minutes} daqiqa"
    if minutes == 0:
        return f"{hours} soat"
    return f"{hours} soat {minutes} daqiqa"


def build_boss_check_in_notification(full_name: str, branch_name: str) -> str:
    from datetime import datetime

    tz = get_settings().tzinfo
    now = datetime.now(tz)
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d.%m.%Y")

    return (
        "🟢 <b>ISHGA KELDI</b>\n\n"
        f"👤 <b>Xodim:</b> {escape(full_name)}\n"
        f"🏪 <b>Filial:</b> {escape(branch_name)}\n"
        f"🕐 <b>Vaqt:</b> {time_str}\n"
        f"📅 <b>Sana:</b> {date_str}"
    )


def build_boss_check_out_notification(full_name: str, branch_name: str, attendance) -> str:
    tz = get_settings().tzinfo

    check_in_time = (
        attendance.check_in_at.astimezone(tz).strftime("%H:%M")
        if attendance.check_in_at
        else "--:--"
    )
    check_out_time = (
        attendance.check_out_at.astimezone(tz).strftime("%H:%M")
        if attendance.check_out_at
        else "--:--"
    )
    date_str = (
        attendance.check_out_at.astimezone(tz).strftime("%d.%m.%Y")
        if attendance.check_out_at
        else ""
    )

    duration_str = "0 daqiqa"
    if attendance.check_in_at and attendance.check_out_at:
        hours, minutes = CheckInService.calculate_work_duration_static(
            attendance.check_in_at, attendance.check_out_at
        )
        duration_str = format_duration(hours, minutes)

    return (
        "🔴 <b>ISHDAN KETDI</b>\n\n"
        f"👤 <b>Xodim:</b> {escape(full_name)}\n"
        f"🏪 <b>Filial:</b> {escape(branch_name)}\n"
        f"🟢 <b>Kelgan vaqti:</b> {check_in_time}\n"
        f"🔴 <b>Ketgan vaqti:</b> {check_out_time}\n"
        f"⏱️ <b>Ish vaqti:</b> {duration_str}\n"
        f"📅 <b>Sana:</b> {date_str}"
    )

