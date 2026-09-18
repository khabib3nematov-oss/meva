from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.attendance import Attendance
    from app.models.user import User


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (
        CheckConstraint("allowed_radius_meters > 0", name="allowed_radius_meters_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    address: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    allowed_radius_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    employees: Mapped[list["User"]] = relationship(
        back_populates="branch",
        foreign_keys="User.branch_id",
    )
    attendances: Mapped[list["Attendance"]] = relationship(back_populates="branch")
