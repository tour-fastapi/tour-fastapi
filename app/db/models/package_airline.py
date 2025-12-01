from __future__ import annotations
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER


class PackageAirline(Base):
    __tablename__ = "package_airlines"

    # FK → packages.package_id   (must NOT autoincrement)
    package_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("packages.package_id", ondelete="CASCADE"),
        primary_key=True
    )

    # FK → airlines.airline_id  (also PK in many-to-many)
    airline_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("airlines.airline_id", ondelete="CASCADE"),
        primary_key=True
    )

    # relationships
    package = relationship("Package", back_populates="package_airlines")
    airline = relationship("Airline", back_populates="packages")

    __table_args__ = (
        UniqueConstraint("package_id", "airline_id", name="uq_package_airline"),
    )
