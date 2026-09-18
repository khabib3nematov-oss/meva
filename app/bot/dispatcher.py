from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.handlers import setup_routers
from app.bot.middlewares import DatabaseSessionMiddleware


def create_dispatcher(
    session_maker: async_sessionmaker[AsyncSession] | None = None,
) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    if session_maker is not None:
        dispatcher.update.middleware(DatabaseSessionMiddleware(session_maker))
    setup_routers(dispatcher)
    return dispatcher
