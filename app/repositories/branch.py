from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch


class BranchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_branches(self) -> list[Branch]:
        statement = select(Branch).where(Branch.is_active == True)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def get_by_id(self, branch_id: int) -> Branch | None:
        statement = select(Branch).where(Branch.id == branch_id)
        return await self._session.scalar(statement)
