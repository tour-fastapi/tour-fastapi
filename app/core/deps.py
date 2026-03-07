# app/core/deps.py
from typing import Annotated
from fastapi import Query
from app.db.session import get_db

# We’ll reuse these for pagination later:
Page = Annotated[int, Query(1, ge=1)]
Limit = Annotated[int, Query(10, ge=1, le=100)]