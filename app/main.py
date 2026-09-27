import asyncio
from contextlib import suppress
import logging
import os

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
from sqlalchemy.exc import SQLAlchemyError

from app.bot.dispatcher import create_dispatcher
from app.config import get_settings
from app.database.session import (
    create_async_engine_from_settings,
    create_session_maker,
    ping_database,
)
from app.logging_config import configure_logging
from app.services.reminders import run_worker_reminders


async def healthcheck(_: web.Request) -> web.Response:
    return web.Response(text="OK")


async def run_health_server() -> None:
    app = web.Application()
    app.router.add_get("/", healthcheck)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )
    await site.start()

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def run_bot() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    bot = Bot(
        token=settings.required_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    engine = create_async_engine_from_settings(settings)
    session_maker = create_session_maker(engine)
    dispatcher = create_dispatcher(session_maker)
    health_server_task = asyncio.create_task(run_health_server())
    reminder_task = asyncio.create_task(
        run_worker_reminders(bot, session_maker, settings.tzinfo)
    )

    try:
        if settings.boss_channel_id:
            try:
                boss_chat = await bot.get_chat(settings.boss_channel_id)
                logger.info(
                    "boss_chat_verified",
                    extra={
                        "boss_chat_id": boss_chat.id,
                        "boss_chat_type": boss_chat.type,
                        "boss_chat_title": boss_chat.title,
                    },
                )
            except Exception:
                logger.exception(
                    "boss_chat_verification_failed",
                    extra={"boss_chat_id": str(settings.boss_channel_id)},
                )
        else:
            logger.warning("boss_chat_not_configured")

        await ping_database(engine)
        logger.info(
            "database_connection_verified",
            extra={"timezone": settings.timezone},
        )
        logger.info("bot_polling_started")
        await asyncio.gather(
            dispatcher.start_polling(
                bot,
                allowed_updates=dispatcher.resolve_used_update_types(),
            ),
            health_server_task,
            reminder_task,
        )
    except SQLAlchemyError:
        logger.exception("database_connection_failed")
        raise
    except Exception:
        logger.exception("bot_stopped_with_error")
        raise
    finally:
        health_server_task.cancel()
        reminder_task.cancel()
        with suppress(asyncio.CancelledError):
            await health_server_task
        with suppress(asyncio.CancelledError):
            await reminder_task
        await engine.dispose()
        await bot.session.close()
        logger.info("bot_shutdown_complete")


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
