from __future__ import annotations
from sqlalchemy import Column, Integer, String, DateTime, Numeric, SmallInteger, func
from sqlalchemy.orm import declarative_base
from app.db.base import Base

class Hotel(Base):
    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(255), nullable=False, unique=True)
    city = Column(String(20), nullable=False)  # "Mecca" / "Medinah"

    link = Column(String(500), nullable=True)
    distance_km = Column(Numeric(5, 2), nullable=True)
    rating = Column(SmallInteger, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
