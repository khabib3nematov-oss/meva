from aiogram import Dispatcher

from app.bot.handlers import admin, attendance, check_in, errors, start


def setup_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(admin.router)
    dispatcher.include_router(start.router)
    dispatcher.include_router(check_in.router)
    dispatcher.include_router(attendance.router)
    dispatcher.include_router(errors.router)
