from datetime import datetime
from html import escape

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.repositories import AttendanceRepository, UserRepository
from app.services.check_in import CheckInService

router = Router(name=__name__)


def format_duration(hours: int, minutes: int) -> str:
    if hours == 0 and minutes == 0:
        return "0 daqiqa"
    if hours == 0:
        return f"{minutes} daqiqa"
    if minutes == 0:
        return f"{hours} soat"
    return f"{hours} soat {minutes} daqiqa"


@router.message(F.text == "📋 MENING DAVOMATIM")
async def handle_my_attendance_request(message: Message, session: AsyncSession) -> None:
    """Handle '📋 MENING DAVOMATIM' button press to display employee attendance report."""
    if message.from_user is None:
        await message.answer("Foydalanuvchi ma'lumotlari topilmadi.")
        return

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)

    if user is None:
        await message.answer("Hisobingiz topilmadi. Iltimos, /start buyrug'ini bosing.")
        return

    attendance_repo = AttendanceRepository(session)
    tz = get_settings().tzinfo
    now = datetime.now(tz)

    monthly_records = await attendance_repo.get_monthly_attendances(
        user.id, now.year, now.month
    )
    recent_records = await attendance_repo.get_recent_attendances(user.id, limit=7)

    if not recent_records:
        await message.answer(
            f"📋 <b>MENING DAVOMATIM</b>\n\n"
            f"👤 <b>Xodim:</b> {escape(user.full_name)}\n\n"
            "Sizda hali davomat ma'lumotlari mavjud emas."
        )
        return

    # Calculate monthly totals
    total_days = len({rec.work_date for rec in monthly_records if rec.check_in_at})
    total_seconds = 0
    for rec in monthly_records:
        if rec.check_in_at and rec.check_out_at:
            total_seconds += int((rec.check_out_at - rec.check_in_at).total_seconds())

    monthly_hours = total_seconds // 3600
    monthly_minutes = (total_seconds % 3600) // 60
    monthly_duration_str = format_duration(monthly_hours, monthly_minutes)

    lines = [
        "📋 <b>MENING DAVOMATIM</b>\n",
        f"👤 <b>Xodim:</b> {escape(user.full_name)}",
        f"📊 <b>Ushbu oy:</b> {total_days} ish kuni | Jami: {monthly_duration_str}\n",
        "─── <b>OXIRGI DAVOMATLAR</b> ───",
    ]

    for rec in recent_records:
        date_str = rec.work_date.strftime("%d.%m.%Y")
        branch_name = rec.branch.name if rec.branch else "Filial"

        check_in_time = (
            rec.check_in_at.astimezone(tz).strftime("%H:%M")
            if rec.check_in_at
            else "--:--"
        )
        check_out_time = (
            rec.check_out_at.astimezone(tz).strftime("%H:%M")
            if rec.check_out_at
            else "--:--"
        )

        if rec.check_in_at and rec.check_out_at:
            h, m = CheckInService.calculate_work_duration_static(
                rec.check_in_at, rec.check_out_at
            )
            duration_text = format_duration(h, m)
            status_line = f"🟢 {check_in_time} — 🔴 {check_out_time} ({duration_text})"
        elif rec.check_in_at:
            status_line = f"🟢 {check_in_time} — <i>Ishda</i>"
        else:
            status_line = "<i>Ma'lumot yo'q</i>"

        lines.append(f"\n▫️ <b>{date_str}</b> — <i>{escape(branch_name)}</i>\n   {status_line}")

    await message.answer("\n".join(lines))
