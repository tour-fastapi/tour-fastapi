from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, ForeignKey, DECIMAL, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.db.base import Base


class PackagePrice(Base):
    __tablename__ = "package_prices"

    # Primary key
    id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    # FK → packages.package_id (unsigned)
    package_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("packages.package_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Price variants (match what your /package/new route uses)
    price_single: Mapped[Optional[float]] = mapped_column(
        DECIMAL(10, 2),
        nullable=True,
    )
    price_double: Mapped[Optional[float]] = mapped_column(
        DECIMAL(10, 2),
        nullable=True,
    )
    price_triple: Mapped[Optional[float]] = mapped_column(
        DECIMAL(10, 2),
        nullable=True,
    )
    price_quad: Mapped[Optional[float]] = mapped_column(
        DECIMAL(10, 2),
        nullable=True,
    )

    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Backref from Package.price_row
    package = relationship(
        "Package",
        back_populates="price_row",
    )
