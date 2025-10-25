# app/db/models/package_airline.py
from __future__ import annotations
from sqlalchemy import Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class PackageAirline(Base):
    __tablename__ = "package_airlines"

    package_id: Mapped[int] = mapped_column(ForeignKey("packages.package_id", ondelete="CASCADE"), primary_key=True)
    airline_id: Mapped[int] = mapped_column(ForeignKey("airlines.airline_id", ondelete="CASCADE"), primary_key=True)

    package = relationship("Package", back_populates="package_airlines")
    airline = relationship("Airline", back_populates="packages")

    __table_args__ = (
        UniqueConstraint("package_id", "airline_id", name="uq_package_airline"),
    )
