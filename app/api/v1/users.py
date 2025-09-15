from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.deps import get_db
from app.db.models.user import User
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user.
    - Validates request with UserCreate (email format, etc.)
    - Checks unique email
    - Inserts into DB and returns the row as UserOut
    """
    # uniqueness check
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already exists")

    user = User(
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        personal_email=payload.personal_email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.get("", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Optional search by email/first/last"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List users (very basic).
    - Supports optional q search and pagination (limit/offset)
    """
    qs = db.query(User)
    if q:
        ilike = f"%{q.lower()}%"
        qs = qs.filter(
            (User.email.ilike(ilike)) |
            (User.first_name.ilike(ilike)) |
            (User.last_name.ilike(ilike))
        )
    rows = qs.order_by(User.id.desc()).offset(offset).limit(limit).all()
    return rows

@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    Get a single user by ID.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
