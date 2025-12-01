from __future__ import annotations
from typing import Optional, Literal
from sqlalchemy import String, Date, Enum, ForeignKey, DateTime
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

Leg = Literal["onward", "return"]

class PackageFlight(Base):
    __tablename__ = "package_flights"

    id: Mapped[int] = mapped_column(MYSQL_INTEGER(unsigned=True), primary_key=True, autoincrement=True)

    package_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("packages.package_id", ondelete="CASCADE"),
        nullable=False
    )

    leg: Mapped[Leg] = mapped_column(Enum("onward", "return", name="flight_leg"), nullable=False)
    flight_date: Mapped[Optional[Date]] = mapped_column(Date)
    flight_type: Mapped[Optional[str]] = mapped_column(Enum("direct", "via", name="flight_type"))
    via_city: Mapped[Optional[str]] = mapped_column(String(100))
    airline_name: Mapped[Optional[str]] = mapped_column(String(120))

    created_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    package = relationship("Package", back_populates="flights")
