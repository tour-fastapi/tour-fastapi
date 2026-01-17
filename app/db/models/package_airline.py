from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.db.mixins import Base

class PackageAirline(Base):
    __tablename__ = "package_airlines"

    package_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("packages.package_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # airlines.airline_id is SIGNED in your DB, so keep it signed here
    airline_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=False),
        ForeignKey("airlines.airline_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # ✅ ADD THESE (THIS IS WHAT YOUR ERROR IS ABOUT)
    package = relationship("Package", back_populates="package_airlines")
    airline = relationship("Airline", back_populates="package_airlines",overlaps="package_airlines,packages")

    __table_args__ = (
        UniqueConstraint("package_id", "airline_id", name="uq_package_airline"),
    )
