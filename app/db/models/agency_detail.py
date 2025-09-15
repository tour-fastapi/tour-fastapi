from __future__ import annotations
from typing import Optional
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

class AgencyDetail(Base):
    __tablename__ = "agency_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.registration_id"), nullable=False, unique=True)

    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city:          Mapped[Optional[str]] = mapped_column(String(100))
    state:         Mapped[Optional[str]] = mapped_column(String(100))
    country:       Mapped[Optional[str]] = mapped_column(String(100))
    postal_code:   Mapped[Optional[str]] = mapped_column(String(20))
    website:       Mapped[Optional[str]] = mapped_column(String(255))   # NEW

    contact1_name:  Mapped[Optional[str]] = mapped_column(String(100))
    contact1_phone: Mapped[Optional[str]] = mapped_column(String(30))
    contact2_name:  Mapped[Optional[str]] = mapped_column(String(100))
    contact2_phone: Mapped[Optional[str]] = mapped_column(String(30))

    created_at: Mapped[Optional["DateTime"]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional["DateTime"]] = mapped_column(DateTime, server_default=func.now())

    agency = relationship("Agency", back_populates="detail")
