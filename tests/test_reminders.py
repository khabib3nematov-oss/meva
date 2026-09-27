from datetime import datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, User, UserRole
from app.services.reminders import get_next_reminder_at, send_worker_reminder


def test_next_reminder_is_morning_before_0800() -> None:
    timezone = ZoneInfo("Asia/Tashkent")
    now = datetime(2026, 9, 27, 7, 59, tzinfo=timezone)

    assert get_next_reminder_at(now) == datetime(2026, 9, 27, 8, 0, tzinfo=timezone)


def test_next_reminder_after_0800_is_2200() -> None:
    timezone = ZoneInfo("Asia/Tashkent")
    now = datetime(2026, 9, 27, 8, 0, tzinfo=timezone)

    assert get_next_reminder_at(now) == datetime(2026, 9, 27, 22, 0, tzinfo=timezone)


def test_next_reminder_after_2200_is_next_day_morning() -> None:
    timezone = ZoneInfo("Asia/Tashkent")
    now = datetime(2026, 9, 27, 22, 1, tzinfo=timezone)

    assert get_next_reminder_at(now) == datetime(2026, 9, 28, 8, 0, tzinfo=timezone)


async def test_reminder_sends_only_to_active_employees_and_managers() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all(
            [
                User(telegram_id=101, full_name="Employee", role=UserRole.EMPLOYEE),
                User(telegram_id=102, full_name="Manager", role=UserRole.MANAGER),
                User(telegram_id=103, full_name="Owner", role=UserRole.OWNER),
                User(
                    telegram_id=104,
                    full_name="Inactive",
                    role=UserRole.EMPLOYEE,
                    is_active=False,
                ),
            ]
        )
        await session.commit()

    bot = SimpleNamespace(send_message=AsyncMock())
    await send_worker_reminder(bot, session_maker, time(8, 0))

    assert {call.kwargs["chat_id"] for call in bot.send_message.await_args_list} == {
        101,
        102,
    }
    await engine.dispose()