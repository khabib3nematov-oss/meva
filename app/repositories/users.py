from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy import update as sql_update
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

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def decide_registration_request(
        self,
        user_id: int,
        *,
        approved: bool,
        decided_by_telegram_id: int,
    ) -> bool:
        decision = "APPROVED" if approved else "REJECTED"
        statement = (
            sql_update(User)
            .where(User.id == user_id, User.approval_status == "PENDING")
            .values(
                approval_status=decision,
                is_active=approved,
                approval_decided_by_telegram_id=decided_by_telegram_id,
                approval_decided_at=datetime.now(timezone.utc),
            )
        )
        result = await self._session.execute(statement)
        return result.rowcount == 1

    async def get_active_workers_for_reminders(self) -> list[User]:
        statement = select(User).where(
            User.is_active.is_(True),
            User.telegram_id.isnot(None),
            User.role.in_([UserRole.EMPLOYEE, UserRole.MANAGER]),
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def create_user(
        self,
        telegram_id: int,
        full_name: str,
        phone: str | None = None,
        role: UserRole = UserRole.EMPLOYEE,
        approval_status: str = "PENDING",
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            phone=phone,
            role=role,
            approval_status=approval_status,
            is_active=approval_status == "APPROVED",
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user
