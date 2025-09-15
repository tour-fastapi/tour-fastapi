# app/db/models/package.py
from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String, Text, DECIMAL, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Package(Base):
    __tablename__ = "packages"

    package_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("agencies.registration_id"), nullable=False)

    package_name: Mapped[str] = mapped_column(String(255), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[Optional["DateTime"]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agency = relationship("Agency", back_populates="packages")
    
    flights   = relationship("PackageFlight", back_populates="package", cascade="all, delete-orphan")
    stays     = relationship("PackageStay",   back_populates="package", cascade="all, delete-orphan")
    inclusion = relationship("PackageInclusion", uselist=False, back_populates="package", cascade="all, delete-orphan")
    itineraries = relationship(
        "PackageItinerary",
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="PackageItinerary.day_number"
    )