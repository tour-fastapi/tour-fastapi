from __future__ import annotations
from typing import Optional, Literal
from sqlalchemy import String, Date, Enum, ForeignKey, DateTime
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

StayCity = Literal["Mecca", "Medinah"]

class PackageStay(Base):
    __tablename__ = "package_stays"

    id: Mapped[int] = mapped_column(MYSQL_INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("packages.package_id", ondelete="CASCADE"),
        nullable=False
    )

    city: Mapped[StayCity] = mapped_column(Enum("Mecca", "Medinah", name="stay_city"), nullable=False)
    check_in: Mapped[Optional["Date"]] = mapped_column(Date)
    check_out: Mapped[Optional["Date"]] = mapped_column(Date)
    hotel_name: Mapped[Optional[str]] = mapped_column(String(200))
    hotel_link: Mapped[Optional[str]] = mapped_column(String(300))
    distance_text: Mapped[Optional[str]] = mapped_column(String(120))
    distance_m: Mapped[Optional[int]] = mapped_column(MYSQL_INTEGER(unsigned=False))  # meters; can be plain INT
    created_at: Mapped[Optional["DateTime"]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    package = relationship("Package", back_populates="stays")
