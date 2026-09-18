from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AttendanceStatus

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.user import User


class Attendance(TimestampMixin, Base):
    __tablename__ = "attendances"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", name="uq_attendances_employee_work_date"),
        Index("ix_attendances_employee_id", "employee_id"),
        Index("ix_attendances_branch_work_date", "branch_id", "work_date"),
        Index("ix_attendances_status", "status"),
        Index("ix_attendances_check_in_at", "check_in_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_in_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    check_in_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    check_out_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    check_out_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    check_in_distance_meters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    check_out_distance_meters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status"),
        nullable=False,
    )

    employee: Mapped["User"] = relationship(
        back_populates="attendances",
        foreign_keys=[employee_id],
    )
    branch: Mapped["Branch"] = relationship(back_populates="attendances")
