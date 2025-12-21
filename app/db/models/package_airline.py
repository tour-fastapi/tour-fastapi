from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.db.mixins import Base

class PackageAirline(Base):
    __tablename__ = "package_airlines"

    # packages.package_id is INT UNSIGNED
    package_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("packages.package_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # airlines.airline_id is INT (SIGNED) in your DB
    airline_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=False),
        ForeignKey("airlines.airline_id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (
        UniqueConstraint("package_id", "airline_id", name="uq_package_airline"),
    )
