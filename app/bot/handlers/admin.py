from datetime import datetime
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.repositories.attendance import AttendanceRepository


router = Router(name=__name__)


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