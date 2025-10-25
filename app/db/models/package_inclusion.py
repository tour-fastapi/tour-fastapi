# app/db/models/package_inclusion.py

from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    Boolean,
    Text,
    DateTime,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

# ---- Robust Base import (works with either base.py or base_class.py) ----
try:
    from app.db.base import Base  # type: ignore
except ModuleNotFoundError:
    try:
        from app.db.base_class import Base  # type: ignore
    except ModuleNotFoundError:
        from sqlalchemy.orm import declarative_base
        Base = declarative_base()  # type: ignore


class PackageInclusion(Base):
    __tablename__ = "package_inclusions"

    id = Column(Integer, primary_key=True, index=True)

    # FK to packages
    package_id = Column(
        Integer,
        ForeignKey("packages.package_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ✅ Add the matching relationship expected by Package.inclusion.back_populates="package"
    package = relationship("Package", back_populates="inclusion")

    # New checkbox + description fields
    meals_enabled        = Column(Boolean, nullable=False, default=False)
    meals_desc           = Column(Text, nullable=True)

    laundry_enabled      = Column(Boolean, nullable=False, default=False)
    laundry_desc         = Column(Text, nullable=True)

    transport_enabled    = Column(Boolean, nullable=False, default=False)
    transport_desc       = Column(Text, nullable=True)

    zamzam_enabled       = Column(Boolean, nullable=False, default=False)
    zamzam_desc          = Column(Text, nullable=True)

    welcome_kit_enabled  = Column(Boolean, nullable=False, default=False)
    welcome_kit_desc     = Column(Text, nullable=True)

    insurance_enabled    = Column(Boolean, nullable=False, default=False)
    insurance_desc       = Column(Text, nullable=True)

    other_notes          = Column(Text, nullable=True)

    created_at           = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("package_id", name="uq_package_inclusions_package_id"),
    )
