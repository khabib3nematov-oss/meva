from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import LeaveType

if TYPE_CHECKING:
    from app.models.user import User


class Leave(Base):
    __tablename__ = "leaves"
    __table_args__ = (
        CheckConstraint("date_to >= date_from", name="date_to_on_or_after_date_from"),
        Index("ix_leaves_employee_dates", "employee_id", "date_from", "date_to"),
        Index("ix_leaves_approved_by", "approved_by"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[LeaveType] = mapped_column(Enum(LeaveType, name="leave_type"), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    employee: Mapped["User"] = relationship(
        back_populates="leaves",
        foreign_keys=[employee_id],
    )
    approver: Mapped["User | None"] = relationship(
        back_populates="approved_leaves",
        foreign_keys=[approved_by],
    )
