from __future__ import annotations
from typing import Optional
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class AgencyTestimonial(Base):
    __tablename__ = "agency_testimonials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK → agencies.registration_id
    agency_id: Mapped[int] = mapped_column(
        ForeignKey("agencies.registration_id", ondelete="CASCADE"),
        nullable=False
    )

    author_name: Mapped[Optional[str]] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger)

    created_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, server_default=func.now())

    agency = relationship("Agency", back_populates="testimonials")
