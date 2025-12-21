# app/db/base.py
from app.db.mixins import Base
from app.db.session import engine

__all__ = ["Base", "engine"]
