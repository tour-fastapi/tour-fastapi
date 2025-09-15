# app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(plain_password, password_hash)

# JWT helpers
# - We put "type" claim so we can distinguish "access" vs "refresh"
def create_token(user_id: int, expires_delta: timedelta, token_type: str = "access") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGO)

def decode_token(token: str, token_type: Optional[str] = None) -> dict:
    """
    Decode and validate a JWT. If token_type is provided, also checks the 'type' claim.
    Raises ValueError on any validation problem.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGO])
    except JWTError as e:
        raise ValueError("Invalid token") from e

    # Optional type check
    if token_type is not None:
        if payload.get("type") != token_type:
            raise ValueError("Wrong token type")

    # Basic required claim
    if "sub" not in payload:
        raise ValueError("Invalid token payload (missing 'sub')")

    return payload
