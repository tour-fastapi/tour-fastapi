from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

class PackageCreate(BaseModel):
    registration_id: int
    package_name: str
    days: int
    price: Decimal
    description: str | None = None

class PackageOut(BaseModel):
    package_id: int
    registration_id: int
    package_name: str
    days: int
    price: Decimal
    description: str | None
    created_at: datetime

    class Config:
        from_attributes = True
