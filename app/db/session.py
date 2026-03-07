# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.core.config import settings

db_url = settings.DATABASE_URL.strip()
db_url = db_url.replace("mysql+mysqldb://", "mysql+pymysql://")
connect_args = {}
if "mysql+pymysql://" in db_url:
    connect_args = {"ssl": {}}

engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=2,
    max_overflow=0,
    pool_timeout=15,
    pool_use_lifo=True,
    future=True,
    connect_args=connect_args,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
