# app/db/models/agency.py
from __future__ import annotations

from typing import Optional, List
from app.db.models.agency_detail import AgencyDetail

from sqlalchemy import Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Agency(Base):
    __tablename__ = "agencies"

    registration_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agencies_name: Mapped[str] = mapped_column(String(255), nullable=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    country: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id"), nullable=True)

    created_at: Mapped[Optional["DateTime"]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="agencies")
    city_rel = relationship("City", back_populates="agencies")

    packages: Mapped[List["Package"]] = relationship(
        "Package",
        back_populates="agency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # ✅ NEW: inquiries relationship to match Inquiry.agency
    inquiries: Mapped[List["Inquiry"]] = relationship(
        "Inquiry",
        back_populates="agency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    packages = relationship(
    "Package",
    back_populates="agency",
    cascade="all, delete-orphan",
    )
    # One-to-one detail (add this block)
        # One-to-one relationship
 # 1:1 child row with extra info about the agency
    # single-detail 1:1
    detail = relationship("AgencyDetail", back_populates="agency", uselist=False, cascade="all, delete-orphan")

# testimonials 1:N
    testimonials = relationship("AgencyTestimonial", back_populates="agency", cascade="all, delete-orphan", lazy="selectin")


