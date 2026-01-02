from sqlalchemy import (
    Column,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.dialects.mysql import TINYINT

# ---- Base import ----
from app.db.base import Base


class PackageInclusion(Base):
    __tablename__ = "package_inclusions"

    # Primary key
    id: Mapped[int] = mapped_column(MYSQL_INTEGER(unsigned=True), primary_key=True, autoincrement=True)

    # Foreign key → MUST match packages.package_id EXACT TYPE
    package_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("packages.package_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # relationship back to Package
    package = relationship("Package", back_populates="inclusion")

    meals_enabled = Column(Boolean, nullable=False, default=False)
    meals_desc = Column(Text)

    laundry_enabled = Column(Boolean, nullable=False, default=False)
    laundry_desc = Column(Text)

    transport_enabled = Column(Boolean, nullable=False, default=False)
    transport_desc = Column(Text)

    zamzam_enabled = Column(Boolean, nullable=False, default=False)
    zamzam_desc = Column(Text)

    welcome_kit_enabled = Column(Boolean, nullable=False, default=False)
    welcome_kit_desc = Column(Text)

    insurance_enabled = Column(Boolean, nullable=False, default=False)
    insurance_desc = Column(Text)

    visa_enabled = Column(TINYINT(1), nullable=False, server_default="0")
    visa_desc = Column(Text, nullable=True)

    ziyarat_enabled = Column(TINYINT(1), nullable=False, server_default="0")
    ziyarat_desc = Column(Text, nullable=True)

    other_notes = Column(Text)

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint("package_id", name="uq_package_inclusions_package_id"),
    )
