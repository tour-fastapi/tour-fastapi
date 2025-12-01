from __future__ import annotations
from typing import Optional, List

from sqlalchemy import Integer, String, Text, DECIMAL, ForeignKey, DateTime, SmallInteger, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Package(Base):
    __tablename__ = "packages"

    from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

    package_id: Mapped[int] = mapped_column(MYSQL_INTEGER(unsigned=True), primary_key=True, autoincrement=True)



    # FK → agencies.registration_id
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("agencies.registration_id", ondelete="CASCADE"), nullable=False
    )

    package_type: Mapped[str] = mapped_column(String(10), nullable=False)
    package_name: Mapped[str] = mapped_column(String(255), nullable=False)
    package_class: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    travel_month: Mapped[Optional[int]] = mapped_column(SmallInteger)
    travel_year:  Mapped[Optional[int]] = mapped_column(SmallInteger)

    created_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    agency = relationship("Agency", back_populates="packages")

    flights = relationship(
        "PackageFlight", back_populates="package",
        cascade="all, delete-orphan", lazy="selectin"
    )

    stays = relationship(
        "PackageStay", back_populates="package",
        cascade="all, delete-orphan", lazy="selectin"
    )

    inclusion = relationship(
        "PackageInclusion",
        back_populates="package",
        uselist=False,
        cascade="all, delete-orphan"
    )

    price_row = relationship(
        "PackagePrice",
        uselist=False,
        back_populates="package",
        cascade="all, delete-orphan"
    )

    itineraries = relationship(
        "PackageItinerary",
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="PackageItinerary.day_number"
    )

    package_airlines = relationship(
        "PackageAirline",
        back_populates="package",
        cascade="all, delete-orphan"
    )

    airlines = relationship(
        "Airline",
        secondary="package_airlines",
        viewonly=True
    )

    theme = relationship(
        "PackageTheme",
        uselist=False,
        back_populates="package",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("travel_month BETWEEN 1 AND 12", name="ck_packages_month"),
        CheckConstraint("travel_year >= 2026", name="ck_packages_year"),
    )
