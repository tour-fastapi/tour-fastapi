# app/db/models/agency.py
from __future__ import annotations

from typing import Optional, List
from datetime import datetime

from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Agency(Base):
    __tablename__ = "agencies"

    # Primary key
    registration_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Ownership
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    # Core identity
    agencies_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Contact
    agency_email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Location (OPTIONAL in DB; match schema)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)      # matches DEFAULT NULL
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)   # matches DEFAULT NULL

    # Optional profile fields
    description: Mapped[Optional[str]] = mapped_column(Text)
    public_registration_code: Mapped[Optional[str]] = mapped_column(String(100))
    website_url: Mapped[Optional[str]] = mapped_column(String(255))
    facebook_url: Mapped[Optional[str]] = mapped_column(String(255))
    instagram_url: Mapped[Optional[str]] = mapped_column(String(255))

    # Stats (all optional)
    operating_since: Mapped[Optional[int]] = mapped_column(Integer)
    num_umrah_tours: Mapped[Optional[int]] = mapped_column(Integer)
    num_hajj_tours: Mapped[Optional[int]] = mapped_column(Integer)
    num_pilgrims_sent: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )

    # City FK (optional helper to cities table)
    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id", ondelete="SET NULL"),
                                                   index=True, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="agencies")

    # optional relationship to City; respects ON DELETE SET NULL
    city_rel: Mapped[Optional["City"]] = relationship(
        "City",
        back_populates="agencies",
        passive_deletes=True,
        lazy="selectin",
    )

    packages: Mapped[List["Package"]] = relationship(
        "Package",
        back_populates="agency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    inquiries: Mapped[List["Inquiry"]] = relationship(
        "Inquiry",
        back_populates="agency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    branches: Mapped[List["AgencyBranch"]] = relationship(
        "AgencyBranch",
        back_populates="agency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    testimonials: Mapped[List["AgencyTestimonial"]] = relationship(
        "AgencyTestimonial",
        back_populates="agency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Agency id={self.registration_id!r} name={self.agencies_name!r} city={self.city!r}>"


    logo_path = Column(String(255), nullable=True)
    logo_uploaded_at = Column(DateTime, nullable=True)
    logo_width = Column(Integer, nullable=True)
    logo_height = Column(Integer, nullable=True)