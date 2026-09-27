from datetime import datetime
from html import escape
import logging
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.repositories.attendance import AttendanceRepository
from app.repositories.users import UserRepository


router = Router(name=__name__)
logger = logging.getLogger(__name__)


class CheckoutCorrectionStates(StatesGroup):
    WAITING_FOR_TIME = State()


def parse_checkout_correction_time(value: str, timezone: ZoneInfo) -> datetime | None:
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y %H:%M").replace(
            tzinfo=timezone
        )
    except ValueError:
        return None


def format_daily_admin_report(records: list, now: datetime) -> str:
    if not records:
        return (
            f"📊 <b>BUGUNGI DAVOMAT</b>\n"
            f"📅 {now.strftime('%d.%m.%Y')}\n\n"
            "Bugun hali hech kim kelmagan."
        )

    working = [record for record in records if not record.check_out_at]
    finished = [record for record in records if record.check_out_at]
    lines = [
        "📊 <b>BUGUNGI DAVOMAT</b>",
        f"📅 {now.strftime('%d.%m.%Y')}",
        f"👥 Jami kelganlar: <b>{len(records)}</b>",
        f"🟢 Hozir ishda: <b>{len(working)}</b>",
        f"✅ Ishni tugatgan: <b>{len(finished)}</b>",
    ]

    def append_section(title: str, section_records: list) -> None:
        if not section_records:
            return
        lines.extend(["", title, ""])
        for index, record in enumerate(section_records, start=1):
            check_in_time = (
                record.check_in_at.astimezone(now.tzinfo).strftime("%H:%M")
                if record.check_in_at
                else "--:--"
            )
            branch_name = escape(record.branch.name if record.branch else "Filial")
            employee_name = escape(
                record.employee.full_name if record.employee else "Xodim"
            )
            status = "🟢 Ishda" if not record.check_out_at else "✅ Ketgan"
            lines.append(f"{index}. <b>{employee_name}</b> — {check_in_time} — {status}")
            lines.append(f"   🏪 {branch_name}")

    append_section("🟢 <b>HOZIR ISHLAYOTGANLAR</b>", working)
    append_section("✅ <b>ISHNI TUGATGANLAR</b>", finished)
    return "\n".join(lines)


@router.message(Command("admin"))
async def handle_admin_report(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return

    if message.from_user.id not in get_settings().owner_ids:
        await message.answer("Bu buyruq faqat rahbarlar uchun.")
        return

    timezone = get_settings().tzinfo
    now = datetime.now(timezone)
    records = await AttendanceRepository(session).get_by_work_date(now.date())
    await message.answer(format_daily_admin_report(records, now))


async def decide_registration_request(
    callback: CallbackQuery,
    session: AsyncSession,
    *,
    approved: bool,
) -> None:
    settings = get_settings()
    if callback.from_user.id not in settings.owner_ids:
        await callback.answer("Bu amal faqat rahbarlar uchun.", show_alert=True)
        return

    try:
        user_id = int((callback.data or "").split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri ariza.", show_alert=True)
        return

    user_repository = UserRepository(session)
    user = await user_repository.get_by_id(user_id)
    if user is None:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return

    changed = await user_repository.decide_registration_request(
        user_id,
        approved=approved,
        decided_by_telegram_id=callback.from_user.id,
    )
    if not changed:
        await callback.answer("Bu ariza avval ko'rib chiqilgan.", show_alert=True)
        return
    await session.commit()

    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.exception(
                "failed_to_remove_registration_decision_buttons",
                extra={"user_id": user_id},
            )

    decision_text = "tasdiqlandi" if approved else "rad etildi"
    await callback.answer(f"Ariza {decision_text}.")
    if callback.bot and user.telegram_id:
        worker_message = (
            "✅ Arizangiz tasdiqlandi. Endi botdan foydalanishingiz mumkin. /start ni bosing."
            if approved
            else "Arizangiz rahbar tomonidan rad etildi. Ma'lumot uchun rahbarga murojaat qiling."
        )
        try:
            await callback.bot.send_message(
                chat_id=user.telegram_id,
                text=worker_message,
            )
        except Exception:
            logger.exception(
                "failed_to_notify_worker_about_registration_decision",
                extra={"telegram_id": user.telegram_id, "approved": approved},
            )


@router.callback_query(F.data.startswith("registration_approve:"))
async def handle_registration_approval(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    await decide_registration_request(callback, session, approved=True)


@router.callback_query(F.data.startswith("registration_reject:"))
async def handle_registration_rejection(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    await decide_registration_request(callback, session, approved=False)


@router.callback_query(F.data.startswith("checkout_fix:"))
async def handle_checkout_fix_request(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if callback.from_user.id not in get_settings().owner_ids:
        await callback.answer("Bu amal faqat rahbarlar uchun.", show_alert=True)
        return
    if not isinstance(callback.message, Message):
        await callback.answer("Xabar endi mavjud emas.", show_alert=True)
        return

    try:
        attendance_id = int((callback.data or "").split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri davomat yozuvi.", show_alert=True)
        return

    attendance = await AttendanceRepository(session).get_by_id(attendance_id)
    if attendance is None or attendance.check_out_at is not None:
        await callback.answer("Bu smena allaqachon yopilgan yoki topilmadi.", show_alert=True)
        return

    await state.set_state(CheckoutCorrectionStates.WAITING_FOR_TIME)
    await state.update_data(attendance_id=attendance_id)
    await callback.answer()
    await callback.message.answer(
        "Smenaning haqiqiy tugash vaqtini yuboring formatda "
        "<code>ДД.ММ.ГГГГ ЧЧ:ММ</code>.\n"
        "Masalan: <code>26.09.2026 21:45</code>.\n"
        "Bekor qilish uchun yuboring: <code>bekor</code>."
    )


@router.callback_query(F.data.startswith("checkout_keep:"))
async def handle_checkout_keep_open(callback: CallbackQuery) -> None:
    if callback.from_user.id not in get_settings().owner_ids:
        await callback.answer("Bu amal faqat rahbarlar uchun.", show_alert=True)
        return
    await callback.answer(
        "Smena ochiq qoldirildi. Yangi kelish xodim uchun hozircha bloklangan.",
        show_alert=True,
    )


@router.message(CheckoutCorrectionStates.WAITING_FOR_TIME, F.text)
async def handle_checkout_correction_time(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if message.from_user is None or message.from_user.id not in get_settings().owner_ids:
        await state.clear()
        return
    if message.text and message.text.strip().casefold() == "bekor":
        await state.clear()
        await message.answer("Tuzatish bekor qilindi. Smena ochiq qoldi.")
        return

    timezone = get_settings().tzinfo
    checkout_at = parse_checkout_correction_time(message.text or "", timezone)
    if checkout_at is None:
        await message.answer(
            "Vaqt formati noto'g'ri. <code>ДД.ММ.ГГГГ ЧЧ:ММ</code> ko'rinishida yuboring."
        )
        return

    state_data = await state.get_data()
    attendance_id = state_data.get("attendance_id")
    attendance_repo = AttendanceRepository(session)
    attendance = (
        await attendance_repo.get_by_id(attendance_id)
        if isinstance(attendance_id, int)
        else None
    )
    if attendance is None or attendance.check_out_at is not None:
        await state.clear()
        await message.answer("Smena topilmadi yoki boshqa rahbar uni allaqachon yopgan.")
        return

    check_in_at = attendance.check_in_at
    if check_in_at is None:
        await state.clear()
        await message.answer("Smenada kelish vaqti yo'q; tuzatish bajarilmadi.")
        return
    if check_in_at.tzinfo is None:
        check_in_at = check_in_at.replace(tzinfo=timezone)
    else:
        check_in_at = check_in_at.astimezone(timezone)

    now = datetime.now(timezone)
    if checkout_at <= check_in_at or checkout_at > now:
        await message.answer(
            "Chiqish vaqti kelish vaqtidan keyin va hozirgi vaqtdan kech bo'lmasligi "
            "kerak. Sana va vaqtni qayta yuboring."
        )
        return

    await attendance_repo.correct_check_out(
        attendance=attendance,
        check_out_at=checkout_at,
        corrected_by_telegram_id=message.from_user.id,
    )
    await state.clear()
    employee_name = escape(attendance.employee.full_name if attendance.employee else "Xodim")
    await message.answer(
        f"✅ Смена {employee_name} закрыта временем "
        f"<b>{checkout_at.strftime('%d.%m.%Y %H:%M')}</b>. Исправление записано."
    )
    if message.bot and attendance.employee and attendance.employee.telegram_id:
        try:
            await message.bot.send_message(
                chat_id=attendance.employee.telegram_id,
                text=(
                    "Rahbar kechagi davomat yozuvingizni tuzatdi. "
                    "Endi yangi kelishni belgilashingiz mumkin."
                ),
            )
        except Exception:
            logger.exception(
                "failed_to_notify_employee_after_checkout_correction",
                extra={"attendance_id": attendance.id},
            )