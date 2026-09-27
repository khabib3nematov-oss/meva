import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.users import UserRepository
from app.services.onboarding import (
    EmployeeOnboardingService,
    OnboardingError,
    OnboardingErrorCode,
    account_access_message,
)
from app.utils.phone import normalize_phone_number


class FakeUserRepository:
    def __init__(self, users: list[User] | None = None) -> None:
        self.users = users or []

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return next((user for user in self.users if user.telegram_id == telegram_id), None)

    async def get_by_phone(self, phone: str) -> User | None:
        return next((user for user in self.users if user.phone == phone), None)

    async def create_user(
        self,
        telegram_id: int,
        full_name: str,
        phone: str | None = None,
        role: UserRole = UserRole.EMPLOYEE,
        approval_status: str = "PENDING",
    ) -> User:
        user = User(
            id=len(self.users) + 1,
            telegram_id=telegram_id,
            full_name=full_name,
            phone=phone,
            role=role,
            approval_status=approval_status,
            is_active=approval_status == "APPROVED",
        )
        self.users.append(user)
        return user


def make_user(
    *,
    phone: str | None = None,
    telegram_id: int | None = None,
    is_active: bool = True,
    full_name: str = "Ali Valiyev",
) -> User:
    return User(
        id=1,
        telegram_id=telegram_id,
        full_name=full_name,
        phone=phone,
        role=UserRole.EMPLOYEE,
        branch_id=1,
        is_active=is_active,
    )


def test_normalize_phone_number_for_uzbek_local_number() -> None:
    assert normalize_phone_number("90 123-45-67") == "+998901234567"


async def test_register_new_user_without_phone() -> None:
    repo = FakeUserRepository()
    service = EmployeeOnboardingService(repo)

    registered = await service.register_new_user(
        telegram_id=100,
        full_name="Ali Valiyev",
    )

    assert registered.telegram_id == 100
    assert registered.full_name == "Ali Valiyev"
    assert registered.phone is None
    assert registered.approval_status == "PENDING"
    assert registered.is_active is False
    assert len(repo.users) == 1


async def test_register_new_user_returns_existing_if_already_registered() -> None:
    existing = make_user(telegram_id=100, full_name="Ali Valiyev")
    repo = FakeUserRepository([existing])
    service = EmployeeOnboardingService(repo)

    registered = await service.register_new_user(
        telegram_id=100,
        full_name="Ali Valiyev Updated",
    )

    assert registered is existing
    assert len(repo.users) == 1


async def test_register_new_user_rejects_existing_phone() -> None:
    existing = make_user(phone="+998901234567")
    repo = FakeUserRepository([existing])
    service = EmployeeOnboardingService(repo)

    with pytest.raises(OnboardingError) as exc_info:
        await service.register_new_user(
            telegram_id=200,
            full_name="Boshqa Xodim",
            phone_number="+998901234567",
        )

    assert exc_info.value.code == OnboardingErrorCode.PHONE_ALREADY_EXISTS


def test_pending_and_rejected_users_receive_access_messages() -> None:
    pending = make_user(is_active=False)
    pending.approval_status = "PENDING"
    rejected = make_user(is_active=False)
    rejected.approval_status = "REJECTED"

    assert "kutmoqda" in (account_access_message(pending) or "")
    assert "rad etildi" in (account_access_message(rejected) or "")


async def test_owner_can_approve_a_pending_user_only_once() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        user = User(
            telegram_id=987654,
            full_name="New Employee",
            role=UserRole.EMPLOYEE,
            approval_status="PENDING",
            is_active=False,
        )
        session.add(user)
        await session.commit()
        user_id = user.id

        repository = UserRepository(session)
        approved = await repository.decide_registration_request(
            user_id,
            approved=True,
            decided_by_telegram_id=1002484373,
        )
        await session.commit()
        await session.refresh(user)

        assert approved is True
        assert user.approval_status == "APPROVED"
        assert user.is_active is True
        assert user.approval_decided_by_telegram_id == 1002484373
        assert user.approval_decided_at is not None
        assert (
            await repository.decide_registration_request(
                user_id,
                approved=False,
                decided_by_telegram_id=5867823541,
            )
            is False
        )

    await engine.dispose()
