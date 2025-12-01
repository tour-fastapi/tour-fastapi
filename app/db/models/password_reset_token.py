from __future__ import annotations
from typing import Optional
from datetime import datetime

from sqlalchemy import DateTime, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.db.base import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        primary_key=True,
        autoincrement=True
    )

    # FK to users.id (MUST match user.id type → unsigned integer)
    user_id: Mapped[int] = mapped_column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("users.id"),
        nullable=False
    )

    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    user = relationship("User", back_populates="password_reset_tokens")
