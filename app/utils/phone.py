import re


_DIGITS_RE = re.compile(r"\D+")


def normalize_phone_number(phone_number: str) -> str:
    """Normalize phone numbers to a stable international digit string."""

    digits = _DIGITS_RE.sub("", phone_number)

    if digits.startswith("00"):
        digits = digits[2:]

    if len(digits) == 9:
        digits = f"998{digits}"

    if len(digits) < 10 or len(digits) > 15:
        raise ValueError("Phone number must contain 10 to 15 digits.")

    return f"+{digits}"
