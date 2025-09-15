from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.deps import get_db
from app.db.models.agency import Agency
from app.schemas.agency import AgencyCreate, AgencyOut

router = APIRouter(prefix="/agencies", tags=["agencies"])

@router.post("", response_model=AgencyOut, status_code=status.HTTP_201_CREATED)
def create_agency(payload: AgencyCreate, db: Session = Depends(get_db)):
    """
    Create an agency (legacy-compatible).
    - Takes user_id from body for now (we'll switch to JWT on Day 6).
    """
    agency = Agency(
        agencies_name=payload.agencies_name,
        user_id=payload.user_id,
        country=payload.country,
        city=payload.city,
        description=payload.description,
        city_id=payload.city_id,
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return agency

@router.get("", response_model=List[AgencyOut])
def list_agencies(
    db: Session = Depends(get_db),
    user_id: Optional[int] = Query(None, description="Filter by owner user_id (temporary, replaced by JWT later)"),
    q: Optional[str] = Query(None, description="Search by name/city/country"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List agencies with optional filters and pagination.
    """
    qs = db.query(Agency)
    if user_id is not None:
        qs = qs.filter(Agency.user_id == user_id)
    if q:
        ilike = f"%{q.lower()}%"
        qs = qs.filter(
            (Agency.agencies_name.ilike(ilike)) |
            (Agency.city.ilike(ilike)) |
            (Agency.country.ilike(ilike))
        )
    rows = qs.order_by(Agency.registration_id.desc()).offset(offset).limit(limit).all()
    return rows

@router.get("/{registration_id}", response_model=AgencyOut)
def get_agency(registration_id: int, db: Session = Depends(get_db)):
    """
    Get a single agency by its legacy PK (registration_id).
    """
    agency = db.query(Agency).filter(Agency.registration_id == registration_id).first()
    if not agency:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agency not found")
    return agency

@router.put("/{registration_id}", response_model=AgencyOut)
def update_agency(registration_id: int, payload: AgencyCreate, db: Session = Depends(get_db)):
    """
    Update an agency (temporary: accepts user_id in body).
    - Day 6 will replace this with current user from JWT & ownership checks.
    """
    agency = db.query(Agency).filter(Agency.registration_id == registration_id).first()
    if not agency:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agency not found")

    agency.agencies_name = payload.agencies_name
    agency.user_id = payload.user_id
    agency.country = payload.country
    agency.city = payload.city
    agency.description = payload.description
    agency.city_id = payload.city_id

    db.commit()
    db.refresh(agency)
    return agency

@router.delete("/{registration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agency(registration_id: int, db: Session = Depends(get_db)):
    """
    Delete an agency by registration_id.
    - Day 6 will enforce ownership using JWT (user must own the agency).
    """
    agency = db.query(Agency).filter(Agency.registration_id == registration_id).first()
    if not agency:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agency not found")
    db.delete(agency)
    db.commit()
    return
