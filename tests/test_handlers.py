from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.bot.handlers.attendance import format_attendance_report
from app.bot.handlers.admin import format_daily_admin_report
from app.bot.handlers.start import build_employee_menu_text


def test_employee_menu_text_escapes_employee_name_for_html_parse_mode() -> None:
    assert "Ali &amp; Vali" in build_employee_menu_text("Ali & Vali")


def test_attendance_report_includes_summary_and_today_status() -> None:
    timezone = ZoneInfo("Asia/Tashkent")
    now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone)
    record = SimpleNamespace(
        work_date=date(2026, 9, 18),
        check_in_at=datetime(2026, 9, 18, 8, 0, tzinfo=timezone),
        check_out_at=datetime(2026, 9, 18, 17, 30, tzinfo=timezone),
        branch=SimpleNamespace(name="Keles"),
    )

    report = format_attendance_report("Ali Valiyev", [record], [record], now, timezone)

    assert "🗓 <b>Bugun:</b> ✅ Ish kuni yopilgan" in report
    assert "ish kuni" not in report
    assert "• Yopilgan smenalar" not in report
    assert "• Ochiq smenalar" not in report
    assert "• Jami vaqt: <b>9 soat 30 daqiqa</b>" in report
    assert "• O'rtacha smena: <b>9 soat 30 daqiqa</b>" in report


def test_daily_admin_report_lists_employee_time_and_status() -> None:
    timezone = ZoneInfo("Asia/Tashkent")
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone)
    record = SimpleNamespace(
        check_in_at=datetime(2026, 9, 19, 8, 15, tzinfo=timezone),
        check_out_at=None,
        branch=SimpleNamespace(name="Keles"),
        employee=SimpleNamespace(full_name="Ali Valiyev"),
    )

    report = format_daily_admin_report([record], now)

    assert "Jami kelganlar: <b>1</b>" in report
    assert "Ali Valiyev" in report
    assert "08:15" in report
    assert "🟢 Ishda" in report
    assert "🟢 <b>HOZIR ISHLAYOTGANLAR</b>" in report
    assert "🏪 Keles" in report
