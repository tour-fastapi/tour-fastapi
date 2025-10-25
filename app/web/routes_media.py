# app/web/routes_media.py
from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, RedirectResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session
from datetime import datetime
# ⬇ keep get_db from core.deps
from app.core.deps import get_db
# ⬇ auth/session helpers actually live in web.deps
from app.web.deps import require_user, get_csrf_token, require_csrf
from app.db.models.agency import Agency

router = APIRouter()

# ---- Config ----
MEDIA_ROOT = Path("media").resolve()
LOGO_NAME = "logo.webp"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
MAX_W = 2000
MAX_H = 2000


def _agency_dir(registration_id: int) -> Path:
    return MEDIA_ROOT / "agency" / str(registration_id)


def _logo_path(registration_id: int) -> Path:
    return _agency_dir(registration_id) / LOGO_NAME


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _owning_agency_or_403(db: Session, request: Request, registration_id: int) -> Agency:
    user = require_user(request, db)
    ag = (
        db.query(Agency)
        .filter(Agency.registration_id == registration_id)
        .first()
    )
    if not ag:
        raise HTTPException(status_code=404, detail="Agency not found")
    if ag.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return ag


def _read_limited(upload: UploadFile, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"File too large (>{limit} bytes)")
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    return data


def _validate_and_normalize_to_webp(raw: bytes) -> bytes:
    try:
        im = Image.open(BytesIO(raw))
        im.load()
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Unsupported or corrupted image")

    if im.format not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"Only PNG, JPEG or WebP allowed (got {im.format})")

    # Convert/flatten
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    elif im.mode == "RGBA":
        from PIL import Image as PILImage
        bg = PILImage.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        im = bg

    # Resize if huge
    w, h = im.size
    if w > MAX_W or h > MAX_H:
        im.thumbnail((MAX_W, MAX_H))

    out = BytesIO()
    im.save(out, format="WEBP", quality=85, method=6)
    return out.getvalue()


@router.get("/media/agency/{registration_id}/logo")
def get_agency_logo(registration_id: int):
    path = _logo_path(registration_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(path, media_type="image/webp")

@router.post("/agency/{registration_id}/logo")
def upload_agency_logo(
    request: Request,
    registration_id: int,
    file: UploadFile = File(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Upload a logo for an agency.
    - Validates image
    - Converts to WEBP
    - Saves to media/agency/{id}/logo.webp
    - Updates DB metadata
    """
    require_csrf(request, csrf_token)
    agency = _owning_agency_or_403(db, request, registration_id)

    # validate content type
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload must be an image file")

    # read and validate image
    raw = _read_limited(file, MAX_UPLOAD_BYTES)
    webp_bytes = _validate_and_normalize_to_webp(raw)

    # ensure dir
    target_dir = _agency_dir(registration_id)
    _ensure_dir(target_dir)

    tmp_path = target_dir / (LOGO_NAME + ".tmp")
    final_path = _logo_path(registration_id)

    # write to disk
    with open(tmp_path, "wb") as f:
        f.write(webp_bytes)
    os.replace(tmp_path, final_path)

    # update DB
    agency.logo_path = str(final_path)
    agency.logo_uploaded_at = datetime.utcnow()

    # optionally store dimensions
    try:
        from PIL import Image
        img = Image.open(final_path)
        agency.logo_width, agency.logo_height = img.size
    except Exception:
        agency.logo_width = None
        agency.logo_height = None

    db.commit()

    # flash success message (optional)
    from app.web.deps import flash
    flash(request, "Logo uploaded successfully.", "success")

    # redirect back to edit page for confirmation
    return RedirectResponse(
        url=f"/agency/{registration_id}/edit",
        status_code=303,
    )




@router.post("/agency/{registration_id}/logo/remove")
def remove_agency_logo(
    request: Request,
    registration_id: int,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    _owning_agency_or_403(db, request, registration_id)

    p = _logo_path(registration_id)
    if p.exists():
        p.unlink(missing_ok=True)

    return RedirectResponse(url=f"/agency/{registration_id}/dashboard", status_code=303)
