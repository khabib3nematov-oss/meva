import pytest

from app.models.enums import UserRole
from app.models.user import User
from app.services.onboarding import (
    EmployeeOnboardingService,
    OnboardingError,
    OnboardingErrorCode,
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
    ) -> User:
        user = User(
            id=len(self.users) + 1,
            telegram_id=telegram_id,
            full_name=full_name,
            phone=phone,
            role=role,
            is_active=True,
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
