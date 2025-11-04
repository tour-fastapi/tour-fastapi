from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, func
)
from sqlalchemy.orm import relationship
from app.db.base import Base  # adjust path if your Base is elsewhere


class PackageTheme(Base):
    __tablename__ = "package_theme"

    package_id = Column(
        Integer,
        ForeignKey("packages.package_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )

    theme_key = Column(String(32), nullable=False, default="basic", server_default="basic")
    set_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    set_by_user_id = Column(Integer, nullable=True)

    # Relationships
    package = relationship("Package", back_populates="theme")

    # Uncomment if you have a user or users table
    # user = relationship("User", foreign_keys=[set_by_user_id])

    def __repr__(self):
        return f"<PackageTheme package_id={self.package_id} theme_key={self.theme_key}>"
