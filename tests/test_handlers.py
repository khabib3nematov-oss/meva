from app.bot.handlers.start import build_employee_menu_text


def test_employee_menu_text_escapes_employee_name_for_html_parse_mode() -> None:
    assert "Ali &amp; Vali" in build_employee_menu_text("Ali & Vali")
