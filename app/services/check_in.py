from datetime import date, datetime
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo

from app.models.attendance import Attendance
from app.models.branch import Branch
from app.models.user import User


class CheckInErrorCode(StrEnum):
    EMPLOYEE_INACTIVE = "EMPLOYEE_INACTIVE"
    EMPLOYEE_NO_BRANCH = "EMPLOYEE_NO_BRANCH"
    DUPLICATE_CHECK_IN = "DUPLICATE_CHECK_IN"
    OUTSIDE_RADIUS = "OUTSIDE_RADIUS"


class CheckOutErrorCode(StrEnum):
    NO_ACTIVE_CHECK_IN = "NO_ACTIVE_CHECK_IN"
    ALREADY_CHECKED_OUT = "ALREADY_CHECKED_OUT"
    OUTSIDE_RADIUS = "OUTSIDE_RADIUS"


class CheckInError(Exception):
    def __init__(self, code: CheckInErrorCode, distance_meters: float | None = None) -> None:
        self.code = code
        self.distance_meters = distance_meters
        super().__init__(code.value)


class CheckOutError(Exception):
    def __init__(self, code: CheckOutErrorCode, distance_meters: float | None = None) -> None:
        self.code = code
        self.distance_meters = distance_meters
        super().__init__(code.value)


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
    ) -> Attendance: ...

    async def update_check_out(
        self,
        attendance: Attendance,
        check_out_at: datetime,
        check_out_latitude: float,
        check_out_longitude: float,
        check_out_distance_meters: float,
    ) -> Attendance: ...


class CheckInService:
    def __init__(self, attendance_repo: AttendanceRepositoryProtocol) -> None:
        self._attendance_repo = attendance_repo
        self._timezone = ZoneInfo("Asia/Tashkent")

    def calculate_distance_meters(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        Returns distance in meters.
        """
        from math import asin, atan2, cos, radians, sin, sqrt

        # Convert decimal degrees to radians
        lat1_rad, lon1_rad = radians(lat1), radians(lon1)
        lat2_rad, lon2_rad = radians(lat2), radians(lon2)

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))

        # Radius of Earth in meters
        r = 6371000
        return c * r

    def get_work_date(self) -> date:
        """Get current work date in Asia/Tashkent timezone."""
        return datetime.now(self._timezone).date()

    async def validate_check_in(
        self,
        employee: User,
        branch: Branch | None,
        latitude: float,
        longitude: float,
    ) -> tuple[bool, float | None]:
        """
        Validate check-in request.
        Returns (is_valid, distance_meters).
        Raises CheckInError for validation failures.
        """
        if not employee.is_active:
            raise CheckInError(CheckInErrorCode.EMPLOYEE_INACTIVE)

        if branch is None:
            raise CheckInError(CheckInErrorCode.EMPLOYEE_NO_BRANCH)

        work_date = self.get_work_date()
        existing_attendance = await self._attendance_repo.get_by_employee_and_date(
            employee.id, work_date
        )
        if existing_attendance is not None:
            raise CheckInError(CheckInErrorCode.DUPLICATE_CHECK_IN)

        distance_meters = self.calculate_distance_meters(
            latitude,
            longitude,
            float(branch.latitude),
            float(branch.longitude),
        )

        if distance_meters > branch.allowed_radius_meters:
            raise CheckInError(
                CheckInErrorCode.OUTSIDE_RADIUS, distance_meters=distance_meters
            )

        return True, distance_meters

    async def create_attendance(
        self,
        employee: User,
        branch: Branch,
        latitude: float,
        longitude: float,
        distance_meters: float,
    ) -> Attendance:
        """Create attendance record after successful validation."""
        work_date = self.get_work_date()
        return await self._attendance_repo.create(
            employee_id=employee.id,
            branch_id=branch.id,
            work_date=work_date,
            check_in_latitude=latitude,
            check_in_longitude=longitude,
            check_in_distance_meters=distance_meters,
        )

    async def process_check_out(self, employee: User) -> Attendance:
        """Process check-out directly without requiring branch selection."""
        if not employee.is_active:
            raise CheckOutError(CheckOutErrorCode.NO_ACTIVE_CHECK_IN)

        attendance = await self._attendance_repo.get_active_check_in(employee.id)
        if attendance is None:
            work_date = self.get_work_date()
            today_attendance = await self._attendance_repo.get_by_employee_and_date(
                employee.id, work_date
            )
            if today_attendance is not None and today_attendance.check_out_at is not None:
                raise CheckOutError(CheckOutErrorCode.ALREADY_CHECKED_OUT)
            raise CheckOutError(CheckOutErrorCode.NO_ACTIVE_CHECK_IN)

        check_out_at = datetime.now(self._timezone)
        return await self._attendance_repo.update_check_out(
            attendance=attendance,
            check_out_at=check_out_at,
            check_out_latitude=attendance.check_in_latitude or 0.0,
            check_out_longitude=attendance.check_in_longitude or 0.0,
            check_out_distance_meters=0.0,
        )

    async def validate_check_out(
        self,
        employee: User,
        branch: Branch | None,
        latitude: float,
        longitude: float,
    ) -> tuple[Attendance, float]:
        """
        Validate check-out request.
        Returns (attendance, distance_meters).
        Raises CheckOutError for validation failures.
        """
        if not employee.is_active:
            raise CheckOutError(CheckOutErrorCode.NO_ACTIVE_CHECK_IN)

        if branch is None:
            raise CheckOutError(CheckOutErrorCode.NO_ACTIVE_CHECK_IN)

        attendance = await self._attendance_repo.get_active_check_in(employee.id)
        if attendance is None:
            # Check if there's a recent attendance that's already checked out
            work_date = self.get_work_date()
            today_attendance = await self._attendance_repo.get_by_employee_and_date(
                employee.id, work_date
            )
            if today_attendance is not None and today_attendance.check_out_at is not None:
                raise CheckOutError(CheckOutErrorCode.ALREADY_CHECKED_OUT)
            raise CheckOutError(CheckOutErrorCode.NO_ACTIVE_CHECK_IN)

        distance_meters = self.calculate_distance_meters(
            latitude,
            longitude,
            float(branch.latitude),
            float(branch.longitude),
        )

        if distance_meters > branch.allowed_radius_meters:
            raise CheckOutError(
                CheckOutErrorCode.OUTSIDE_RADIUS, distance_meters=distance_meters
            )

        return attendance, distance_meters

    async def update_check_out(
        self,
        attendance: Attendance,
        branch: Branch,
        latitude: float,
        longitude: float,
        distance_meters: float,
    ) -> Attendance:
        """Update attendance record with check-out data."""
        check_out_at = datetime.now(self._timezone)
        return await self._attendance_repo.update_check_out(
            attendance=attendance,
            check_out_at=check_out_at,
            check_out_latitude=latitude,
            check_out_longitude=longitude,
            check_out_distance_meters=distance_meters,
        )

    def calculate_work_duration(
        self, check_in_at: datetime, check_out_at: datetime
    ) -> tuple[int, int]:
        """
        Calculate work duration between check-in and check-out.
        Returns (hours, minutes).
        """
        duration = check_out_at - check_in_at
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return hours, minutes

    @staticmethod
    def calculate_work_duration_static(
        check_in_at: datetime, check_out_at: datetime
    ) -> tuple[int, int]:
        """
        Static method to calculate work duration between check-in and check-out.
        Returns (hours, minutes).
        """
        duration = check_out_at - check_in_at
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return hours, minutes
