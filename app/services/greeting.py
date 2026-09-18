def build_start_message(full_name: str | None) -> str:
    display_name = full_name or "there"
    return (
        f"Hello, {display_name}!\n\n"
        "MEVACHI attendance bot is online.\n"
        "Attendance recording is not enabled yet. Please contact your manager if you need access."
    )
