from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.attendance import Attendance
from app.models.branch import Branch
from app.models.enums import UserRole
from app.models.user import User
from app.services.check_in import (
    CheckInError,
    CheckInErrorCode,
    CheckInService,
    CheckOutError,
    CheckOutErrorCode,
)


class FakeAttendanceRepository:
    def __init__(self, attendances: list[Attendance] | None = None) -> None:
        self.attendances = attendances or []
        self.create_calls: list[dict] = []
        self.update_check_out_calls: list[dict] = []

    async def get_by_employee_and_date(
        self, employee_id: int, work_date: date
    ) -> Attendance | None:
        return next(
            (
                att
                for att in self.attendances
                if att.employee_id == employee_id and att.work_date == work_date
            ),
            None,
        )

    async def get_active_check_in(self, employee_id: int) -> Attendance | None:
        return next(
            (
                att
                for att in self.attendances
                if att.employee_id == employee_id
                and att.check_in_at is not None
                and att.check_out_at is None
            ),
            None,
        )

    async def create(
        self,
        employee_id: int,
        branch_id: int,
        work_date: date,
        check_in_latitude: float,
        check_in_longitude: float,
        check_in_distance_meters: float,
    ) -> Attendance:
        attendance = Attendance(
            employee_id=employee_id,
            branch_id=branch_id,
            work_date=work_date,
            check_in_latitude=Decimal(str(check_in_latitude)),
            check_in_longitude=Decimal(str(check_in_longitude)),
            check_in_distance_meters=Decimal(str(check_in_distance_meters)),
            status="PRESENT",
        )
        self.create_calls.append(
            {
                "employee_id": employee_id,
                "branch_id": branch_id,
                "work_date": work_date,
                "check_in_latitude": check_in_latitude,
                "check_in_longitude": check_in_longitude,
                "check_in_distance_meters": check_in_distance_meters,
            }
        )
        self.attendances.append(attendance)
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
        attendance.check_out_latitude = Decimal(str(check_out_latitude))
        attendance.check_out_longitude = Decimal(str(check_out_longitude))
        attendance.check_out_distance_meters = Decimal(str(check_out_distance_meters))
        self.update_check_out_calls.append(
            {
                "attendance": attendance,
                "check_out_at": check_out_at,
                "check_out_latitude": check_out_latitude,
                "check_out_longitude": check_out_longitude,
                "check_out_distance_meters": check_out_distance_meters,
            }
        )
        return attendance


def make_user(
    *,
    phone: str = "+998901234567",
    telegram_id: int = 100,
    is_active: bool = True,
    full_name: str = "Ali Valiyev",
    branch_id: int | None = 1,
) -> User:
    return User(
        telegram_id=telegram_id,
        full_name=full_name,
        phone=phone,
        role=UserRole.EMPLOYEE,
        branch_id=branch_id,
        is_active=is_active,
    )


def make_branch(
    *,
    id: int = 1,
    name: str = "Toshkent Filiali",
    latitude: float = 41.311150,
    longitude: float = 69.279730,
    allowed_radius_meters: int = 100,
) -> Branch:
    return Branch(
        id=id,
        name=name,
        latitude=Decimal(str(latitude)),
        longitude=Decimal(str(longitude)),
        allowed_radius_meters=allowed_radius_meters,
        is_active=True,
    )


def test_haversine_distance_calculation() -> None:
    """Test Haversine formula distance calculation."""
    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    # Test distance between two known points (approximately 1 km apart)
    distance = service.calculate_distance_meters(
        lat1=41.311150,
        lon1=69.279730,
        lat2=41.321150,
        lon2=69.289730,
    )

    # Distance should be approximately 1.4 km (1400 meters)
    assert 1300 < distance < 1500


def test_haversine_distance_same_point() -> None:
    """Test that distance between same point is zero."""
    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    distance = service.calculate_distance_meters(
        lat1=41.311150,
        lon1=69.279730,
        lat2=41.311150,
        lon2=69.279730,
    )

    assert distance == 0.0


async def test_valid_check_in_within_radius() -> None:
    """Test successful check-in when employee is within allowed radius."""
    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    employee = make_user(branch_id=1)
    branch = make_branch(allowed_radius_meters=100)

    # Employee is at branch location (0 meters away)
    is_valid, distance = await service.validate_check_in(
        employee=employee,
        branch=branch,
        latitude=41.311150,
        longitude=69.279730,
    )

    assert is_valid is True
    assert distance == 0.0

    # Create attendance
    attendance = await service.create_attendance(
        employee=employee,
        branch=branch,
        latitude=41.311150,
        longitude=69.279730,
        distance_meters=0.0,
    )

    assert attendance.employee_id == employee.id
    assert attendance.branch_id == branch.id
    assert attendance.check_in_distance_meters == Decimal("0.00")


async def test_check_in_outside_radius_fails() -> None:
    """Test that check-in fails when employee is outside allowed radius."""
    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    employee = make_user(branch_id=1)
    branch = make_branch(allowed_radius_meters=100)

    # Employee is 1.4 km away (outside 100m radius)
    with pytest.raises(CheckInError) as exc_info:
        await service.validate_check_in(
            employee=employee,
            branch=branch,
            latitude=41.321150,
            longitude=69.289730,
        )

    assert exc_info.value.code == CheckInErrorCode.OUTSIDE_RADIUS
    assert exc_info.value.distance_meters is not None
    assert exc_info.value.distance_meters > 100


async def test_duplicate_check_in_fails() -> None:
    """Test that duplicate check-in for same workday fails."""
    employee = make_user(branch_id=1)
    existing_attendance = Attendance(
        employee_id=employee.id,
        branch_id=1,
        work_date=date.today(),
        status="PRESENT",
    )
    repo = FakeAttendanceRepository([existing_attendance])
    service = CheckInService(repo)

    branch = make_branch()

    with pytest.raises(CheckInError) as exc_info:
        await service.validate_check_in(
            employee=employee,
            branch=branch,
            latitude=41.311150,
            longitude=69.279730,
        )

    assert exc_info.value.code == CheckInErrorCode.DUPLICATE_CHECK_IN


async def test_inactive_employee_check_in_fails() -> None:
    """Test that inactive employee cannot check in."""
    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    employee = make_user(branch_id=1, is_active=False)
    branch = make_branch()

    with pytest.raises(CheckInError) as exc_info:
        await service.validate_check_in(
            employee=employee,
            branch=branch,
            latitude=41.311150,
            longitude=69.279730,
        )

    assert exc_info.value.code == CheckInErrorCode.EMPLOYEE_INACTIVE


async def test_employee_without_branch_check_in_fails() -> None:
    """Test that employee without assigned branch cannot check in."""
    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    employee = make_user(branch_id=None)

    with pytest.raises(CheckInError) as exc_info:
        await service.validate_check_in(
            employee=employee,
            branch=None,
            latitude=41.311150,
            longitude=69.279730,
        )

    assert exc_info.value.code == CheckInErrorCode.EMPLOYEE_NO_BRANCH


async def test_check_in_at_edge_of_radius() -> None:
    """Test check-in near the allowed radius boundary (inside)."""
    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    employee = make_user(branch_id=1)
    branch = make_branch(allowed_radius_meters=100)

    # Calculate a point 99 meters away (just inside the radius)
    # For small distances, we can approximate: 1 degree latitude ≈ 111,000 meters
    # So 99 meters ≈ 0.00089 degrees
    edge_latitude = 41.311150 + (99.0 / 111000.0)

    is_valid, distance = await service.validate_check_in(
        employee=employee,
        branch=branch,
        latitude=edge_latitude,
        longitude=69.279730,
    )

    assert is_valid is True
    assert 98 <= distance <= 100  # Allow small rounding error


async def test_check_in_just_outside_radius() -> None:
    """Test check-in just outside the allowed radius fails."""
    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    employee = make_user(branch_id=1)
    branch = make_branch(allowed_radius_meters=100)

    # Calculate a point 101 meters away (just outside)
    just_outside_latitude = 41.311150 + (101.0 / 111000.0)

    with pytest.raises(CheckInError) as exc_info:
        await service.validate_check_in(
            employee=employee,
            branch=branch,
            latitude=just_outside_latitude,
            longitude=69.279730,
        )

    assert exc_info.value.code == CheckInErrorCode.OUTSIDE_RADIUS
    assert exc_info.value.distance_meters > 100


# Check-out tests


async def test_valid_check_out_within_radius() -> None:
    """Test successful check-out when employee is within allowed radius."""
    employee = make_user(branch_id=1)
    branch = make_branch(allowed_radius_meters=100)

    check_in_time = datetime.now()
    attendance = Attendance(
        employee_id=employee.id,
        branch_id=branch.id,
        work_date=date.today(),
        check_in_at=check_in_time,
        check_in_latitude=Decimal("41.311150"),
        check_in_longitude=Decimal("69.279730"),
        check_in_distance_meters=Decimal("0.00"),
        status="PRESENT",
    )

    repo = FakeAttendanceRepository([attendance])
    service = CheckInService(repo)

    # Employee is at branch location (0 meters away)
    validated_attendance, distance = await service.validate_check_out(
        employee=employee,
        branch=branch,
        latitude=41.311150,
        longitude=69.279730,
    )

    assert validated_attendance is attendance
    assert distance == 0.0

    # Update check-out
    updated_attendance = await service.update_check_out(
        attendance=attendance,
        branch=branch,
        latitude=41.311150,
        longitude=69.279730,
        distance_meters=0.0,
    )

    assert updated_attendance.check_out_at is not None
    assert updated_attendance.check_out_latitude == Decimal("41.311150")
    assert updated_attendance.check_out_longitude == Decimal("69.279730")


async def test_check_out_without_active_check_in_fails() -> None:
    """Test that check-out fails when there is no active check-in."""
    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    employee = make_user(branch_id=1)
    branch = make_branch()

    with pytest.raises(CheckOutError) as exc_info:
        await service.validate_check_out(
            employee=employee,
            branch=branch,
            latitude=41.311150,
            longitude=69.279730,
        )

    assert exc_info.value.code == CheckOutErrorCode.NO_ACTIVE_CHECK_IN


async def test_check_out_already_checked_out_fails() -> None:
    """Test that duplicate check-out fails."""
    employee = make_user(branch_id=1)
    branch = make_branch()

    check_in_time = datetime.now()
    check_out_time = datetime.now()
    attendance = Attendance(
        employee_id=employee.id,
        branch_id=branch.id,
        work_date=date.today(),
        check_in_at=check_in_time,
        check_out_at=check_out_time,
        check_in_latitude=Decimal("41.311150"),
        check_in_longitude=Decimal("69.279730"),
        check_out_latitude=Decimal("41.311150"),
        check_out_longitude=Decimal("69.279730"),
        check_in_distance_meters=Decimal("0.00"),
        check_out_distance_meters=Decimal("0.00"),
        status="PRESENT",
    )

    repo = FakeAttendanceRepository([attendance])
    service = CheckInService(repo)

    with pytest.raises(CheckOutError) as exc_info:
        await service.validate_check_out(
            employee=employee,
            branch=branch,
            latitude=41.311150,
            longitude=69.279730,
        )

    assert exc_info.value.code == CheckOutErrorCode.ALREADY_CHECKED_OUT


async def test_check_out_outside_radius_fails() -> None:
    """Test that check-out fails when employee is outside allowed radius."""
    employee = make_user(branch_id=1)
    branch = make_branch(allowed_radius_meters=100)

    check_in_time = datetime.now()
    attendance = Attendance(
        employee_id=employee.id,
        branch_id=branch.id,
        work_date=date.today(),
        check_in_at=check_in_time,
        check_in_latitude=Decimal("41.311150"),
        check_in_longitude=Decimal("69.279730"),
        check_in_distance_meters=Decimal("0.00"),
        status="PRESENT",
    )

    repo = FakeAttendanceRepository([attendance])
    service = CheckInService(repo)

    # Employee is 1.4 km away (outside 100m radius)
    with pytest.raises(CheckOutError) as exc_info:
        await service.validate_check_out(
            employee=employee,
            branch=branch,
            latitude=41.321150,
            longitude=69.289730,
        )

    assert exc_info.value.code == CheckOutErrorCode.OUTSIDE_RADIUS
    assert exc_info.value.distance_meters is not None
    assert exc_info.value.distance_meters > 100


async def test_check_out_inactive_employee_fails() -> None:
    """Test that inactive employee cannot check out."""
    employee = make_user(branch_id=1, is_active=False)
    branch = make_branch()

    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    with pytest.raises(CheckOutError) as exc_info:
        await service.validate_check_out(
            employee=employee,
            branch=branch,
            latitude=41.311150,
            longitude=69.279730,
        )

    assert exc_info.value.code == CheckOutErrorCode.NO_ACTIVE_CHECK_IN


async def test_check_out_employee_without_branch_fails() -> None:
    """Test that employee without assigned branch cannot check out."""
    employee = make_user(branch_id=None)

    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    with pytest.raises(CheckOutError) as exc_info:
        await service.validate_check_out(
            employee=employee,
            branch=None,
            latitude=41.311150,
            longitude=69.279730,
        )

    assert exc_info.value.code == CheckOutErrorCode.NO_ACTIVE_CHECK_IN


def test_work_duration_calculation() -> None:
    """Test work duration calculation."""
    repo = FakeAttendanceRepository()
    service = CheckInService(repo)

    check_in = datetime(2026, 9, 15, 8, 57)
    check_out = datetime(2026, 9, 15, 18, 6)

    hours, minutes = service.calculate_work_duration(check_in, check_out)

    assert hours == 9
    assert minutes == 9


def test_work_duration_calculation_static() -> None:
    """Test static work duration calculation."""
    check_in = datetime(2026, 9, 15, 8, 57)
    check_out = datetime(2026, 9, 15, 18, 6)

    hours, minutes = CheckInService.calculate_work_duration_static(
        check_in, check_out
    )

    assert hours == 9
    assert minutes == 9
