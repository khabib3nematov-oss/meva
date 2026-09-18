from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import UserRole
from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        statement = select(User).where(User.telegram_id == telegram_id)
        return await self._session.scalar(statement)

    async def get_by_telegram_id_with_branch(self, telegram_id: int) -> User | None:
        statement = (
            select(User)
            .where(User.telegram_id == telegram_id)
            .options(selectinload(User.branch))
        )
        return await self._session.scalar(statement)

    async def get_by_phone(self, phone: str) -> User | None:
        statement = select(User).where(User.phone == phone)
        return await self._session.scalar(statement)

    async def create_user(
        self,
        telegram_id: int,
        full_name: str,
        phone: str | None = None,
        role: UserRole = UserRole.EMPLOYEE,
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            phone=phone,
            role=role,
            is_active=True,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user
