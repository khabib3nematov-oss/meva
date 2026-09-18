import asyncio
from app.database.session import create_async_engine_from_settings
from app.config import get_settings
from app.models import Base


async def create_tables():
    settings = get_settings()
    engine = create_async_engine_from_settings(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())
