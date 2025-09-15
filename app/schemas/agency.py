from pydantic import BaseModel
from datetime import datetime

# This is the data we EXPECT from the client when creating an agency (input).
class AgencyCreate(BaseModel):
    agencies_name: str
    country: str
    city: str
    description: str | None = None
    city_id: int | None = None
    user_id: int  # because your legacy schema stores ownership on the agency row

# This is what we RETURN to the client (output).
class AgencyOut(BaseModel):
    registration_id: int
    agencies_name: str
    country: str
    city: str
    description: str | None
    city_id: int | None
    created_at: datetime  # added by TimestampMixin

    class Config:
        # from_attributes=True lets FastAPI convert a SQLAlchemy object -> this Pydantic schema
        from_attributes = True
