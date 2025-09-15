# app/db/models/inquiry.py
from __future__ import annotations

from typing import Optional
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import Column, DateTime
from datetime import datetime, timezone
# inside class Inquiry(Base):


from app.db.base import Base


class Inquiry(Base):
    __tablename__ = "inquiries"

    inquiry_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    inquiry: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(20))

    # FK to agencies.registration_id (per your schema)
    registration_id: Mapped[int] = mapped_column(ForeignKey("agencies.registration_id"), nullable=False)

    created_at: Mapped[Optional["DateTime"]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ↩️ back to Agency
    agency = relationship("Agency", back_populates="inquiries")
