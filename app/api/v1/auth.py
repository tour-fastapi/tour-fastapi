from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from app.core.deps import get_db
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_token, decode_token
from app.db.models.user import User
from app.schemas.auth import SignupIn, LoginIn, TokenPair, TokenUser

router = APIRouter(prefix="/auth", tags=["auth"])

# tells Swagger which URL to use for the "Authorize" password flow
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

@router.post("/signup", response_model=TokenPair, status_code=201)
def signup(data: SignupIn, db: Session = Depends(get_db)):
    # unique email
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already exists")

    user = User(
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        personal_email=data.personal_email,
        password_hash=hash_password(data.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access = create_token(user.id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")
    refresh = create_token(user.id, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh")
    return TokenPair(access_token=access, refresh_token=refresh)

@router.post("/login", response_model=TokenPair)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash) or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    # optional audit
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    access = create_token(user.id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")
    refresh = create_token(user.id, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh")
    return TokenPair(access_token=access, refresh_token=refresh)

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    """
    Dependency used by protected routes:
    - reads Authorization: Bearer <access_token>
    - verifies signature & expiry
    - loads the user from DB and returns it
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
        user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user

@router.get("/me", response_model=TokenUser)
def me(current: User = Depends(get_current_user)):
    return current

@router.post("/refresh", response_model=TokenPair)
def refresh_token(token: str = Depends(oauth2_scheme)):
    """
    Expects the REFRESH token in Authorization header.
    Issues a fresh access + refresh pair.
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
        user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    access = create_token(user_id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")
    refresh = create_token(user_id, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh")
    return TokenPair(access_token=access, refresh_token=refresh)
