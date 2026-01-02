from pydantic import BaseModel
from datetime import datetime

class AgencyCreate(BaseModel):
    agencies_name: str
    country: str
    city: str
    description: str | None = None
    city_id: int | None = None
    user_id: int

class AgencyOut(BaseModel):
    registration_id: int
    agencies_name: str
    country: str
    city: str
    description: str | None
    city_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True
