import asyncio
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.users import UserRepository


logger = logging.getLogger(__name__)

REMINDER_TIMES = (time(8, 0), time(22, 0))
REMINDER_MESSAGES = {
    time(8, 0): (
        "Assalomu alaykum! Ishga yetib kelganingizda 🟢 KELDIM tugmasi orqali "
        "kelganingizni belgilang va fotosurat yuboring."
    ),
    time(22, 0): (
        "Iltimos, ish kuningiz tugagan bo'lsa 🔴 KETDIM tugmasi orqali chiqishni "
        "belgilang va fotosurat yuboring. Agar hali ishda bo'lsangiz, "
        "ishni tugatgach belgilang."
    ),
}


def get_next_reminder_at(now: datetime) -> datetime:
    candidates = [
        datetime.combine(now.date(), reminder_time, tzinfo=now.tzinfo)
        for reminder_time in REMINDER_TIMES
    ]
    upcoming = [candidate for candidate in candidates if candidate > now]
    if upcoming:
        return min(upcoming)

    tomorrow = now.date() + timedelta(days=1)
    return datetime.combine(tomorrow, REMINDER_TIMES[0], tzinfo=now.tzinfo)


async def send_worker_reminder(
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
    reminder_time: time,
) -> None:
    message = REMINDER_MESSAGES[reminder_time]
    async with session_maker() as session:
        workers = await UserRepository(session).get_active_workers_for_reminders()

    sent_count = 0
    failed_count = 0
    for worker in workers:
        if worker.telegram_id is None:
            continue
        try:
            await bot.send_message(chat_id=worker.telegram_id, text=message)
            sent_count += 1
        except TelegramForbiddenError:
            failed_count += 1
            logger.warning(
                "worker_reminder_blocked_by_user",
                extra={"telegram_id": worker.telegram_id},
            )
        except Exception:
            failed_count += 1
            logger.exception(
                "worker_reminder_send_failed",
                extra={"telegram_id": worker.telegram_id},
            )
        await asyncio.sleep(0.05)

    logger.info(
        "worker_reminder_completed",
        extra={
            "reminder_time": reminder_time.strftime("%H:%M"),
            "sent_count": sent_count,
            "failed_count": failed_count,
        },
    )


async def run_worker_reminders(
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
    timezone: ZoneInfo,
) -> None:
    while True:
        now = datetime.now(timezone)
        next_run = get_next_reminder_at(now)
        delay_seconds = max((next_run - now).total_seconds(), 0)
        logger.info(
            "worker_reminder_scheduled",
            extra={"scheduled_at": next_run.isoformat()},
        )
        await asyncio.sleep(delay_seconds)

        try:
            await send_worker_reminder(bot, session_maker, next_run.time())
        except Exception:
            logger.exception(
                "worker_reminder_job_failed",
                extra={"scheduled_at": next_run.isoformat()},
            )