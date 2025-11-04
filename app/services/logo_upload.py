# app/services/logo_upload.py
from __future__ import annotations
import os
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import Tuple
from fastapi import UploadFile, HTTPException
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session
from app.db.models.agency import Agency

MEDIA_ROOT = Path("media").resolve()
LOGO_NAME = "logo.webp"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
MAX_W = 2000
MAX_H = 2000

def agency_dir(registration_id: int) -> Path:
    return MEDIA_ROOT / "agency" / str(registration_id)

def logo_path(registration_id: int) -> Path:
    return agency_dir(registration_id) / LOGO_NAME

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _read_limited(upload: UploadFile, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"File too large (>{limit} bytes)")
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    return data

def _validate_and_normalize_to_webp(raw: bytes) -> bytes:
    try:
        im = Image.open(BytesIO(raw)); im.load()
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Unsupported or corrupted image")

    if im.format not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"Only PNG, JPEG or WebP allowed (got {im.format})")

    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")

    if im.width > MAX_W or im.height > MAX_H:
        im.thumbnail((MAX_W, MAX_H))

    out = BytesIO()
    im.save(out, format="WEBP", quality=85, method=6)
    return out.getvalue()

def save_agency_logo(db: Session, agency: Agency, upload: UploadFile) -> Tuple[int, int]:
    if not upload or not (upload.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload must be an image file")

    raw = _read_limited(upload, MAX_UPLOAD_BYTES)
    webp_bytes = _validate_and_normalize_to_webp(raw)

    _ensure_dir(agency_dir(agency.registration_id))
    tmp_path = logo_path(agency.registration_id).with_suffix(".webp.tmp")
    final_path = logo_path(agency.registration_id)

    with open(tmp_path, "wb") as f:
        f.write(webp_bytes)
    os.replace(tmp_path, final_path)

    agency.logo_path = str(final_path)
    agency.logo_uploaded_at = datetime.utcnow()
    try:
        img = Image.open(final_path)
        agency.logo_width, agency.logo_height = img.size
    except Exception:
        agency.logo_width = None
        agency.logo_height = None

    db.commit()
    return (agency.logo_width or 0, agency.logo_height or 0)
