# app/db/models/package_price.py
from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, ForeignKey, DECIMAL, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

class PackagePrice(Base):
    __tablename__ = "package_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("packages.package_id"), nullable=False, unique=True)

    price_double: Mapped[Optional[float]] = mapped_column(DECIMAL(10, 2))
    price_triple: Mapped[Optional[float]] = mapped_column(DECIMAL(10, 2))
    price_quad:   Mapped[Optional[float]] = mapped_column(DECIMAL(10, 2))
    note:         Mapped[Optional[str]]   = mapped_column(String(255))

    created_at: Mapped[Optional["DateTime"]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional["DateTime"]] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    package = relationship("Package", back_populates="price_row")
