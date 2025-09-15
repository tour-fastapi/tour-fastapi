from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    personal_email: EmailStr | None = None

class UserOut(BaseModel):
    id: int
    email: EmailStr
    first_name: str | None
    last_name: str | None
    personal_email: EmailStr | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
