# app/db/models/city.py
from __future__ import annotations

from typing import List

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Back to agencies; DO NOT use delete-orphan here (agencies are not "owned" by City)
    agencies: Mapped[List["Agency"]] = relationship(
        "Agency",
        back_populates="city_rel",
        passive_deletes=True,   # let DB's ON DELETE SET NULL handle nulling agency.city_id
        lazy="selectin",
    )
