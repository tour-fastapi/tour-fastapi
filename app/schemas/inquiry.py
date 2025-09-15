from pydantic import BaseModel
from datetime import datetime

class InquiryCreate(BaseModel):
    name: str
    phone_number: str
    inquiry: str
    source: str | None = None
    registration_id: int

class InquiryOut(BaseModel):
    inquiry_id: int
    name: str
    phone_number: str
    inquiry: str
    source: str | None
    registration_id: int
    created_at: datetime

    class Config:
        from_attributes = True
