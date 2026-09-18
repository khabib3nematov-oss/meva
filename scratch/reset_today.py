import os
import sys
import asyncio

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete
from app.database.session import create_async_engine_from_settings
from app.config import get_settings
from app.models import Attendance
from sqlalchemy.ext.asyncio import AsyncSession


async def reset_today_attendance():
    settings = get_settings()
    engine = create_async_engine_from_settings(settings)

    async with AsyncSession(engine) as session:
        await session.execute(delete(Attendance))
        await session.commit()
        print("Cleared attendance table successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset_today_attendance())
