import asyncio
from sqlalchemy import delete
from app.database.session import create_async_engine_from_settings
from app.config import get_settings
from app.models import Attendance
from sqlalchemy.ext.asyncio import AsyncSession


async def clean_attendance():
    settings = get_settings()
    engine = create_async_engine_from_settings(settings)
    async with AsyncSession(engine) as session:
        await session.execute(delete(Attendance))
        await session.commit()
        print("Cleaned attendance records successfully!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(clean_attendance())
