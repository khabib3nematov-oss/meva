import asyncio
from sqlalchemy import select
from app.database.session import create_async_engine_from_settings
from app.config import get_settings
from app.models import User, Attendance
from sqlalchemy.ext.asyncio import AsyncSession


async def inspect_db():
    settings = get_settings()
    engine = create_async_engine_from_settings(settings)
    async with AsyncSession(engine) as session:
        users_result = await session.execute(select(User))
        users = users_result.scalars().all()
        print("=== USERS ===")
        for u in users:
            print(f"User ID={u.id}, Name={u.full_name}, TG_ID={u.telegram_id}")

        atts_result = await session.execute(select(Attendance))
        atts = atts_result.scalars().all()
        print("\n=== ATTENDANCE RECORDS ===")
        for a in atts:
            print(
                f"Att ID={a.id}, EmpID={a.employee_id}, Date={a.work_date}, "
                f"CheckIn={a.check_in_at}, CheckOut={a.check_out_at}, BranchID={a.branch_id}"
            )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(inspect_db())
