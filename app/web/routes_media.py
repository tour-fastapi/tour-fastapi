# app/web/routes_media.py
from __future__ import annotations
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.web.deps import require_user, require_csrf, flash
from app.db.models.agency import Agency
from app.services.logo_upload import logo_path, save_agency_logo

router = APIRouter()

def _owning_agency_or_403(db: Session, request: Request, registration_id: int) -> Agency:
    user = require_user(request, db)
    ag = db.query(Agency).filter(Agency.registration_id == registration_id).first()
    if not ag: raise HTTPException(status_code=404, detail="Agency not found")
    if ag.user_id != user.id: raise HTTPException(status_code=403, detail="Not allowed")
    return ag

@router.get("/media/agency/{registration_id}/logo")
def get_agency_logo(registration_id: int):
    p = logo_path(registration_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(p, media_type="image/webp")

@router.post("/agency/{registration_id}/logo")
def upload_agency_logo(
    request: Request,
    registration_id: int,
    file: UploadFile = File(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    agency = _owning_agency_or_403(db, request, registration_id)
    save_agency_logo(db, agency, file)
    flash(request, "Logo uploaded successfully.", "success")
    return RedirectResponse(url=f"/agency/{registration_id}/edit", status_code=303)

@router.post("/agency/{registration_id}/logo/remove")
def remove_agency_logo(
    request: Request,
    registration_id: int,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    _owning_agency_or_403(db, request, registration_id)
    p = logo_path(registration_id)
    if p.exists():
        p.unlink(missing_ok=True)
    return RedirectResponse(url=f"/agency/{registration_id}/dashboard", status_code=303)
