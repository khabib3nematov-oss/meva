from enum import StrEnum
from typing import Protocol

from app.models.enums import UserRole
from app.models.user import User
from app.utils.phone import normalize_phone_number


class OnboardingErrorCode(StrEnum):
    CONTACT_NOT_OWNER = "CONTACT_NOT_OWNER"
    INVALID_PHONE = "INVALID_PHONE"
    PHONE_ALREADY_EXISTS = "PHONE_ALREADY_EXISTS"
    EMPLOYEE_ALREADY_LINKED = "EMPLOYEE_ALREADY_LINKED"


class OnboardingError(Exception):
    def __init__(self, code: OnboardingErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class UserRepositoryProtocol(Protocol):
    async def get_by_telegram_id(self, telegram_id: int) -> User | None: ...

    async def get_by_phone(self, phone: str) -> User | None: ...

    async def create_user(
        self,
        telegram_id: int,
        full_name: str,
        phone: str | None = None,
        role: UserRole = UserRole.EMPLOYEE,
    ) -> User: ...


class EmployeeOnboardingService:
    def __init__(self, users: UserRepositoryProtocol) -> None:
        self._users = users

    async def get_registered_user(self, telegram_id: int) -> User | None:
        return await self._users.get_by_telegram_id(telegram_id)

    async def register_new_user(
        self,
        *,
        telegram_id: int,
        full_name: str,
        phone_number: str | None = None,
    ) -> User:
        registered_user = await self._users.get_by_telegram_id(telegram_id)
        if registered_user is not None:
            return registered_user

        normalized_phone: str | None = None
        if phone_number is not None:
            try:
                normalized_phone = normalize_phone_number(phone_number)
            except ValueError as exc:
                raise OnboardingError(OnboardingErrorCode.INVALID_PHONE) from exc

            existing_user = await self._users.get_by_phone(normalized_phone)
            if existing_user is not None:
                raise OnboardingError(OnboardingErrorCode.PHONE_ALREADY_EXISTS)

        return await self._users.create_user(
            telegram_id=telegram_id,
            full_name=full_name,
            phone=normalized_phone,
            role=UserRole.EMPLOYEE,
        )
