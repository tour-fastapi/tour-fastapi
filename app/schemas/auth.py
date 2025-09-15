# app/schemas/auth.py
from datetime import datetime
from pydantic import BaseModel, EmailStr

class SignupIn(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    personal_email: EmailStr | None = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenUser(BaseModel):
    id: int
    email: EmailStr
    first_name: str | None
    last_name: str | None
    personal_email: EmailStr | None
    created_at: datetime
    updated_at: datetime
