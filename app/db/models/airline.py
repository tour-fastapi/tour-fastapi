# app/db/models/airline.py
from __future__ import annotations
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Airline(Base):
    __tablename__ = "airlines"

    airline_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    packages = relationship("PackageAirline", back_populates="airline", cascade="all, delete-orphan")
