from __future__ import annotations
from typing import Optional
from sqlalchemy import Text, ForeignKey, DateTime
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class PackageItinerary(Base):
    __tablename__ = "package_itineraries"

    id: Mapped[int] = mapped_column(MYSQL_INTEGER(unsigned=True), primary_key=True, autoincrement=True)

    package_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("packages.package_id", ondelete="CASCADE"),
        nullable=False
    )

    day_number: Mapped[int] = mapped_column(MYSQL_INTEGER(unsigned=True), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    package = relationship("Package", back_populates="itineraries")
