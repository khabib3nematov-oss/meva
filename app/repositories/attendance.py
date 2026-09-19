from datetime import date, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance import Attendance
from app.models.user import User


class AttendanceRepositoryProtocol(Protocol):
    async def get_by_employee_and_date(
        self, employee_id: int, work_date: date
    ) -> Attendance | None: ...

    async def get_active_check_in(self, employee_id: int) -> Attendance | None: ...

    async def create(
        self,
        employee_id: int,
        branch_id: int,
        work_date: date,
        check_in_latitude: float,
        check_in_longitude: float,
        check_in_distance_meters: float,
        check_in_at: datetime | None = None,
    ) -> Attendance: ...

    async def update_check_out(
        self,
        attendance: Attendance,
        check_out_at: datetime,
        check_out_latitude: float,
        check_out_longitude: float,
        check_out_distance_meters: float,
    ) -> Attendance: ...

    async def get_recent_attendances(
        self, employee_id: int, limit: int = 7
    ) -> list[Attendance]: ...

    async def get_monthly_attendances(
        self, employee_id: int, year: int, month: int
    ) -> list[Attendance]: ...

    async def get_by_work_date(self, work_date: date) -> list[Attendance]: ...


class AttendanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_employee_and_date(
        self, employee_id: int, work_date: date
    ) -> Attendance | None:
        statement = select(Attendance).where(
            Attendance.employee_id == employee_id, Attendance.work_date == work_date
        )
        return await self._session.scalar(statement)

    async def get_active_check_in(self, employee_id: int) -> Attendance | None:
        statement = (
            select(Attendance)
            .where(
                Attendance.employee_id == employee_id,
                Attendance.check_in_at.isnot(None),
                Attendance.check_out_at.is_(None),
            )
            .options(selectinload(Attendance.branch))
        )
        return await self._session.scalar(statement)

    async def create(
        self,
        employee_id: int,
        branch_id: int,
        work_date: date,
        check_in_latitude: float,
        check_in_longitude: float,
        check_in_distance_meters: float,
        check_in_at: datetime | None = None,
    ) -> Attendance:
        if check_in_at is None:
            from zoneinfo import ZoneInfo
            check_in_at = datetime.now(ZoneInfo("Asia/Tashkent"))

        attendance = Attendance(
            employee_id=employee_id,
            branch_id=branch_id,
            work_date=work_date,
            check_in_at=check_in_at,
            check_in_latitude=check_in_latitude,
            check_in_longitude=check_in_longitude,
            check_in_distance_meters=check_in_distance_meters,
            status="PRESENT",
        )
        self._session.add(attendance)
        await self._session.flush()
        await self._session.refresh(attendance)
        return attendance

    async def update_check_out(
        self,
        attendance: Attendance,
        check_out_at: datetime,
        check_out_latitude: float,
        check_out_longitude: float,
        check_out_distance_meters: float,
    ) -> Attendance:
        attendance.check_out_at = check_out_at
        attendance.check_out_latitude = check_out_latitude
        attendance.check_out_longitude = check_out_longitude
        attendance.check_out_distance_meters = check_out_distance_meters
        self._session.add(attendance)
        await self._session.flush()
        await self._session.refresh(attendance)
        return attendance

    async def get_recent_attendances(
        self, employee_id: int, limit: int = 7
    ) -> list[Attendance]:
        statement = (
            select(Attendance)
            .where(Attendance.employee_id == employee_id)
            .options(selectinload(Attendance.branch))
            .order_by(Attendance.work_date.desc(), Attendance.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def get_monthly_attendances(
        self, employee_id: int, year: int, month: int
    ) -> list[Attendance]:
        from sqlalchemy import extract

        statement = (
            select(Attendance)
            .where(
                Attendance.employee_id == employee_id,
                extract("year", Attendance.work_date) == year,
                extract("month", Attendance.work_date) == month,
            )
            .options(selectinload(Attendance.branch))
            .order_by(Attendance.work_date.desc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def get_by_work_date(self, work_date: date) -> list[Attendance]:
        statement = (
            select(Attendance)
            .where(Attendance.work_date == work_date)
            .options(selectinload(Attendance.employee), selectinload(Attendance.branch))
            .order_by(Attendance.check_in_at.asc(), Attendance.id.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
