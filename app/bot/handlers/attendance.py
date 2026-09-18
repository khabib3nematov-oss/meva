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


def format_attendance_report(
    full_name: str,
    monthly_records: list,
    recent_records: list,
    now: datetime,
    timezone,
) -> str:
    total_days = len({record.work_date for record in monthly_records if record.check_in_at})
    completed_days = sum(
        1 for record in monthly_records if record.check_in_at and record.check_out_at
    )
    open_days = sum(
        1 for record in monthly_records if record.check_in_at and not record.check_out_at
    )
    total_seconds = sum(
        int((record.check_out_at - record.check_in_at).total_seconds())
        for record in monthly_records
        if record.check_in_at and record.check_out_at
    )
    monthly_hours = total_seconds // 3600
    monthly_minutes = (total_seconds % 3600) // 60
    monthly_duration = format_duration(monthly_hours, monthly_minutes)
    average_minutes = total_seconds // completed_days // 60 if completed_days else 0
    average_duration = (
        format_duration(average_minutes // 60, average_minutes % 60)
        if completed_days
        else "-"
    )

    today_record = next(
        (record for record in monthly_records if record.work_date == now.date()),
        None,
    )
    if today_record is None or today_record.check_in_at is None:
        today_status = "⏳ Hali belgilanmagan"
    elif today_record.check_out_at is None:
        today_status = "🟢 Ishda"
    else:
        today_status = "✅ Ish kuni yopilgan"

    lines = [
        "📋 <b>MENING DAVOMATIM</b>",
        f"👤 <b>Xodim:</b> {escape(full_name)}",
        f"📅 <b>Oy:</b> {now.strftime('%B %Y')}",
        f"🗓 <b>Bugun:</b> {today_status}",
        "",
        "📊 <b>OYLIK XULOSA</b>",
        f"• Ishlangan kunlar: <b>{total_days}</b>",
        f"• Yopilgan smenalar: <b>{completed_days}</b>",
        f"• Ochiq smenalar: <b>{open_days}</b>",
        f"• Jami vaqt: <b>{monthly_duration}</b>",
        f"• O'rtacha smena: <b>{average_duration}</b>",
    ]

    if not recent_records:
        lines.append("\nSizda hali davomat ma'lumotlari mavjud emas.")
        return "\n".join(lines)

    lines.extend(["", "─── <b>OXIRGI DAVOMATLAR</b> ───"])
    for record in recent_records:
        date_str = record.work_date.strftime("%d.%m")
        branch_name = escape(record.branch.name if record.branch else "Filial")
        check_in_time = (
            record.check_in_at.astimezone(timezone).strftime("%H:%M")
            if record.check_in_at
            else "--:--"
        )
        check_out_time = (
            record.check_out_at.astimezone(timezone).strftime("%H:%M")
            if record.check_out_at
            else "--:--"
        )

        if record.check_in_at and record.check_out_at:
            hours, minutes = CheckInService.calculate_work_duration_static(
                record.check_in_at, record.check_out_at
            )
            status_line = (
                f"✅ {check_in_time} — {check_out_time} "
                f"({format_duration(hours, minutes)})"
            )
        elif record.check_in_at:
            status_line = f"🟢 {check_in_time} — <i>Ishda</i>"
        else:
            status_line = "<i>Ma'lumot yo'q</i>"

        lines.append(f"\n▫️ <b>{date_str}</b> — <i>{branch_name}</i>\n   {status_line}")

    return "\n".join(lines)


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

    await message.answer(
        format_attendance_report(
            full_name=user.full_name,
            monthly_records=monthly_records,
            recent_records=recent_records,
            now=now,
            timezone=tz,
        )
    )
