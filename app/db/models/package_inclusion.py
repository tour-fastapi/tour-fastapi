from __future__ import annotations
from typing import Optional
from sqlalchemy import String, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class PackageInclusion(Base):
    __tablename__ = "package_inclusions"
    __table_args__ = (UniqueConstraint("package_id", name="ux_inclusion_pkg"),)

    id: Mapped[int] = mapped_column(MYSQL_INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("packages.package_id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    meals: Mapped[Optional[str]] = mapped_column(String(200))
    laundry: Mapped[Optional[str]] = mapped_column(String(200))
    transport: Mapped[Optional[str]] = mapped_column(String(200))
    other_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional["DateTime"]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    package = relationship("Package", back_populates="inclusion")
