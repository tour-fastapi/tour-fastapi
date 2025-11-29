from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Numeric,
    SmallInteger,
    func,
)
from app.db.base import Base


class Hotel(Base):
    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Hotel basic info
    name = Column(String(255), nullable=False, unique=True)
    # DB type can be ENUM('Mecca','Medinah'); here we treat it as a short string
    city = Column(String(20), nullable=False)  # "Mecca" or "Medinah"

    link = Column(String(500), nullable=True)

    # Distance from Haram / Masjid (in kilometers)
    distance_km = Column(Numeric(5, 2), nullable=True)  # e.g. 0.25 = 250 m

    # 1–5 star rating (optional for now)
    rating = Column(SmallInteger, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
