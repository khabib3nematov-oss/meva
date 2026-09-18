from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.attendance import Attendance
    from app.models.audit_log import AuditLog
    from app.models.branch import Branch
    from app.models.leave import Leave
    from app.models.work_schedule import WorkSchedule


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_branch_id", "branch_id"),
        Index("ix_users_role", "role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    branch: Mapped["Branch | None"] = relationship(
        back_populates="employees",
        foreign_keys=[branch_id],
    )
    work_schedules: Mapped[list["WorkSchedule"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        foreign_keys="WorkSchedule.employee_id",
    )
    attendances: Mapped[list["Attendance"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        foreign_keys="Attendance.employee_id",
    )
    leaves: Mapped[list["Leave"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        foreign_keys="Leave.employee_id",
    )
    approved_leaves: Mapped[list["Leave"]] = relationship(
        back_populates="approver",
        foreign_keys="Leave.approved_by",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="actor",
        foreign_keys="AuditLog.actor_id",
    )
