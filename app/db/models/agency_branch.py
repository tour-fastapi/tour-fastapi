# app/db/models/agency_branch.py
from __future__ import annotations
from typing import Optional
from sqlalchemy import Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class AgencyBranch(Base):
    __tablename__ = "agency_branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.registration_id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    contact_person: Mapped[Optional[str]] = mapped_column(String(100))
    contact_number: Mapped[Optional[str]] = mapped_column(String(30))
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    created_at: Mapped[Optional["DateTime"]] = mapped_column(DateTime, server_default=func.now())

    # backref to Agency.branches
    agency = relationship("Agency", back_populates="branches")
