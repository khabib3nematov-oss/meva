from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from app.models.branch import Branch


def build_share_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Telefon raqamni ulashish",
                    request_contact=True,
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Telefon raqamingizni yuboring",
    )


def build_employee_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟢 KELDIM"), KeyboardButton(text="🔴 KETDIM")],
            [KeyboardButton(text="📋 MENING DAVOMATIM")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Amalni tanlang",
    )


def build_branch_selection_keyboard(branches: list[Branch]) -> ReplyKeyboardMarkup:
    keyboard = []
    for i in range(0, len(branches), 2):
        row = [KeyboardButton(text=branches[i].name)]
        if i + 1 < len(branches):
            row.append(KeyboardButton(text=branches[i + 1].name))
        keyboard.append(row)
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Filialni tanlang",
    )
