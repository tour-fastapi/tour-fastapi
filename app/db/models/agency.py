from __future__ import annotations
from typing import Optional, List
from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, ForeignKey, DateTime, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Agency(Base):
    __tablename__ = "agencies"

    # Primary Key
    registration_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Owner (FK → users.id)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    agencies_name: Mapped[str] = mapped_column(String(255), nullable=False)
    agency_email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Optional location
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Optional fields
    description: Mapped[Optional[str]] = mapped_column(Text)
    public_registration_code: Mapped[Optional[str]] = mapped_column(String(100))
    website_url: Mapped[Optional[str]] = mapped_column(String(255))
    facebook_url: Mapped[Optional[str]] = mapped_column(String(255))
    instagram_url: Mapped[Optional[str]] = mapped_column(String(255))

    operating_since: Mapped[Optional[int]] = mapped_column(Integer)
    num_umrah_tours: Mapped[Optional[int]] = mapped_column(Integer)
    num_hajj_tours: Mapped[Optional[int]] = mapped_column(Integer)
    num_pilgrims_sent: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False
    )

    viewed_by_admin = Column(Boolean, nullable=False, default=False)

    # FK to cities table (optional)
    city_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cities.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Relationships
    user = relationship("User", back_populates="agencies")

    city_rel = relationship(
        "City",
        back_populates="agencies",
        passive_deletes=True,
        lazy="selectin"
    )

    packages = relationship(
        "Package",
        back_populates="agency",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    inquiries = relationship(
        "Inquiry",
        back_populates="agency",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    branches = relationship(
        "AgencyBranch",
        back_populates="agency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    testimonials = relationship(
        "AgencyTestimonial",
        back_populates="agency",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # Blocking
    is_blocked = Column(Boolean, nullable=False, default=False)
    blocked_at = Column(DateTime(timezone=True), nullable=True)
    blocked_reason = Column(Text, nullable=True)
    blocked_by_user_id = Column(Integer, nullable=True)

    # Logo metadata
    logo_path = Column(String(255), nullable=True)
    logo_uploaded_at = Column(DateTime, nullable=True)
    logo_width = Column(Integer, nullable=True)
    logo_height = Column(Integer, nullable=True)

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    admin_last_viewed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Agency id={self.registration_id!r} name={self.agencies_name!r}>"
