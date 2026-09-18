import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Dispatcher
from aiogram import BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from aiogram.types import TelegramObject, Update

from app.bot.handlers import setup_routers
from app.bot.middlewares import DatabaseSessionMiddleware


logger = logging.getLogger(__name__)


class RawUpdateLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Update):
            logger.debug(
                "telegram_update_received",
                extra={
                    "update_id": event.update_id,
                    "raw_update": event.model_dump(mode="json", exclude_none=True),
                },
            )
        return await handler(event, data)


def create_dispatcher(
    session_maker: async_sessionmaker[AsyncSession] | None = None,
) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.middleware(RawUpdateLoggingMiddleware())
    if session_maker is not None:
        dispatcher.update.middleware(DatabaseSessionMiddleware(session_maker))
    setup_routers(dispatcher)
    return dispatcher
