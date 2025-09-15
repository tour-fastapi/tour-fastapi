# app/core/deps.py
from typing import Annotated
from fastapi import Query
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# We’ll reuse these for pagination later:
Page = Annotated[int, Query(1, ge=1)]
Limit = Annotated[int, Query(10, ge=1, le=100)]
