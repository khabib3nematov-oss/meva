import asyncio
from decimal import Decimal
from sqlalchemy import select
from app.database.session import create_async_engine_from_settings
from app.config import get_settings
from app.models.branch import Branch
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_branches():
    settings = get_settings()
    engine = create_async_engine_from_settings(settings)
    
    branches_data = [
        {
            "id": 1,
            "name": "1. Keles",
            "address": "Keles",
            "latitude": Decimal("41.380000"),
            "longitude": Decimal("69.200000"),
            "allowed_radius_meters": 100,
        },
        {
            "id": 2,
            "name": "2. Ibn sino",
            "address": "Ibn sino",
            "latitude": Decimal("41.340000"),
            "longitude": Decimal("69.180000"),
            "allowed_radius_meters": 100,
        },
        {
            "id": 3,
            "name": "3. Chorsu",
            "address": "Chorsu",
            "latitude": Decimal("41.327000"),
            "longitude": Decimal("69.235000"),
            "allowed_radius_meters": 100,
        },
        {
            "id": 4,
            "name": "4. Archa kocha",
            "address": "Archa kocha",
            "latitude": Decimal("41.300000"),
            "longitude": Decimal("69.250000"),
            "allowed_radius_meters": 100,
        },
        {
            "id": 5,
            "name": "5. Jarariq",
            "address": "Jarariq",
            "latitude": Decimal("41.360000"),
            "longitude": Decimal("69.190000"),
            "allowed_radius_meters": 100,
        },
    ]

    async with AsyncSession(engine) as session:
        for branch_data in branches_data:
            result = await session.execute(
                select(Branch).where(Branch.id == branch_data["id"])
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.name = branch_data["name"]
                existing.address = branch_data["address"]
                existing.is_active = True
                print(f"Updated branch #{branch_data['id']} -> {branch_data['name']}")
            else:
                branch = Branch(**branch_data, is_active=True)
                session.add(branch)
                print(f"Added branch: {branch_data['name']}")
        
        await session.commit()
        print("Branches seeded successfully!")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_branches())
