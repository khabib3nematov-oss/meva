from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.models import Attendance, Base, Leave, User, WorkSchedule


def test_all_attendance_tables_are_registered() -> None:
    configure_mappers()

    assert set(Base.metadata.tables) == {
        "attendances",
        "audit_logs",
        "branches",
        "leaves",
        "users",
        "work_schedules",
    }


def test_postgresql_enum_type_names_are_explicit() -> None:
    assert User.__table__.c.role.type.name == "user_role"
    assert Attendance.__table__.c.status.type.name == "attendance_status"
    assert Leave.__table__.c.type.type.name == "leave_type"


def test_user_onboarding_columns_are_secure() -> None:
    assert User.__table__.c.telegram_id.nullable is True
    assert User.__table__.c.telegram_id.unique is True
    assert User.__table__.c.phone.nullable is True
    assert User.__table__.c.phone.unique is True


def test_attendance_has_one_record_per_employee_work_date_constraint() -> None:
    unique_constraints = {
        constraint.name: {column.name for column in constraint.columns}
        for constraint in Attendance.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert unique_constraints["uq_attendances_employee_work_date"] == {
        "employee_id",
        "work_date",
    }


def test_work_schedule_has_one_row_per_employee_weekday_constraint() -> None:
    unique_constraints = {
        constraint.name: {column.name for column in constraint.columns}
        for constraint in WorkSchedule.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert unique_constraints["uq_work_schedules_employee_weekday"] == {
        "employee_id",
        "weekday",
    }
