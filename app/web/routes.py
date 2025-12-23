from __future__ import annotations

import hashlib
import random
import re
import secrets
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from app.web.context import ctx as _ctx
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import settings
from app.core.deps import get_db
from app.core.security import create_token, hash_password, verify_password
from app.db.models.agency import Agency
from app.db.models.agency_testimonial import AgencyTestimonial  # (kept if used in templates)
from app.db.models.city import City
from app.db.models.inquiry import Inquiry
from app.db.models import PackageStay
from app.db.models.package import Package
from app.db.models.package_flight import PackageFlight
from app.db.models.package_inclusion import PackageInclusion
from app.db.models.package_itinerary import PackageItinerary
from app.db.models.package_price import PackagePrice
from app.db.models.user import User
from app.services.email_brevo import send_email_brevo
from app.services.otp_session import check_code_and_update, get_otp_ctx, new_otp_ctx
from app.web.deps import (
    COOKIE_NAME,
    flash,
    get_csrf_token,
    get_current_user_from_cookie,
    pop_flashes,
    require_csrf,
    require_user,
)

from datetime import datetime  # you already import datetime above, fine if duplicate
# ⬇ add these
import os
from io import BytesIO
from pathlib import Path
from fastapi import UploadFile, File, HTTPException
from PIL import Image, UnidentifiedImageError

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")

# canonical mapping: DB/user input -> file key (without .html)
THEME_ALIAS_MAP = {
    "premium-aurora": "premium_aurora",
    "premium_aurora": "premium_aurora",
    "aurora": "premium_aurora",

    "premium-classic": "premium",
    "classic": "premium",
    "premium": "premium",

    "basic": "basic",
}

VALID_THEMES = set(THEME_ALIAS_MAP.values())  # {"premium_aurora","premium","basic"}

def normalize_theme_key(raw: str) -> str:
    k = (raw or "basic").strip().lower().replace(" ", "-").replace("_", "-")
    k = THEME_ALIAS_MAP.get(k, "basic")
    return k  # returns one of: premium_aurora | premium | basic


# ----------------- Small helpers -----------------

def _norm(s: str | None) -> str | None:
    s = (s or "").strip()
    return s or None


def _to_date(s: str | None) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def set_access_cookie(resp: Response, token: str):
    resp.set_cookie(
        key=COOKIE_NAME,
        value=f"Bearer {token}",
        httponly=True,
        samesite="lax",
        secure=False,  # set True behind HTTPS in prod
        path="/",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def clear_access_cookie(resp: Response):
    resp.delete_cookie(COOKIE_NAME, path="/")


def set_active_agency(request: Request, registration_id: int | None):
    if registration_id is None:
        request.session.pop("active_agency_id", None)
    else:
        request.session["active_agency_id"] = int(registration_id)


def get_active_agency_id(request: Request) -> int | None:
    return request.session.get("active_agency_id")

# --- Admin helpers + smart redirect after login ---

ADMIN_EMAILS = {"umrahadvisor@gmail.com", "umrahadvisor1@gmail.com"}

def _is_admin_email(email: str | None) -> bool:
    return (email or "").strip().lower() in ADMIN_EMAILS

@router.get("/post-login")
def post_login_redirect(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if user and _is_admin_email(getattr(user, "email", "")):
        return RedirectResponse(url="/admin", status_code=303)
    # fallback to the existing normal flow
    if user:
        return redirect_after_login(request, db, user)
    return RedirectResponse(url="/login", status_code=303)


def redirect_after_login(request: Request, db: Session, user: User) -> RedirectResponse:
    """
    Send the user to the right place after login/OTP:
    - Admins → /admin
    - If user has no agencies → /agency/new (and flash)
    - If user has exactly one agency → that agency dashboard
    - Else → /select-agency
    """
    # --- Admin first ---
    admin_emails = {
        e.strip().lower()
        for e in getattr(settings, "ADMIN_EMAILS", ["umrahadvisor@gmail.com", "umrahadvisor1@gmail.com"])
    }
    if (getattr(user, "is_admin", False)) or (user.email and user.email.lower() in admin_emails):
        return RedirectResponse(url="/admin", status_code=303)

    # --- Regular flow as before ---
    agencies = (
        db.query(Agency)
        .filter(Agency.user_id == user.id)
        .order_by(Agency.registration_id.desc())
        .all()
    )
    if not agencies:
        set_active_agency(request, None)
        flash(request, "Create your first agency.", "info")
        return RedirectResponse(url="/agency/new", status_code=303)

    if len(agencies) == 1:
        set_active_agency(request, agencies[0].registration_id)
        return RedirectResponse(
            url=f"/agency/{agencies[0].registration_id}/dashboard",
            status_code=303,
        )

    set_active_agency(request, None)
    return RedirectResponse(url="/select-agency", status_code=303)

@router.get("/dashboard")
def legacy_dashboard_redirect(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    # Reuse the canonical redirect logic
    return redirect_after_login(request, db, user)



def _send_login_otp(to_email: str, code: str):
    subject = "Your login verification code"
    html = f"""
    <div style="font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
      <h2>Verify your login</h2>
      <p>Use this 6-digit code to complete your login:</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:3px">{code}</p>
      <p>This code expires in {settings.OTP_EXP_MINUTES} minutes.</p>
    </div>
    """
    send_email_brevo(to_email, subject, html)


def _send_register_otp(to_email: str, code: str):
    subject = "Verify your email to finish sign-up"
    html = f"""
    <div style="font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
      <h2>Verify your email</h2>
      <p>Enter this 6-digit code to finish creating your account:</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:3px">{code}</p>
      <p>This code expires in {settings.OTP_EXP_MINUTES} minutes.</p>
    </div>
    """
    send_email_brevo(to_email, subject, html)


def _decode_city(city_name: str) -> str:
    return urllib.parse.unquote(city_name).strip()


# ----------------- Public: Home -----------------

@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    flashes = pop_flashes(request)

    rows = (
        db.query(Agency.city, func.count(Agency.registration_id).label("n"))
        .filter(Agency.city.isnot(None), Agency.city != "")
        .group_by(Agency.city)
        .order_by(func.count(Agency.registration_id).desc(), Agency.city.asc())
        .limit(8)
        .all()
    )
    popular_cities = [
        {
            "name": r[0],
            "count": r[1],
            "operators_href": f"/city/{urllib.parse.quote(r[0])}/umrah_operators",
            "packages_href": f"/city/{urllib.parse.quote(r[0])}/umrah_packages",
            "hub_href": f"/city/{urllib.parse.quote(r[0])}",
        }
        for r in rows
    ]

    return render(
        "home.html",
        request,
        db,
        {
            "title": "Home",
            "flashes": flashes,
            "popular_cities": popular_cities,
        },
        is_public=True,
    )


# --- Footer cities + metrics ---

_footer_cache = {
    "expires": datetime.min.replace(tzinfo=timezone.utc),
    "data": [],
    "limit": 0,
}


def _display_city(a: Agency | None) -> str:
    """Prefer agency.city; else related City.name; else 'Unknown'."""
    if a and a.city and a.city.strip():
        return a.city.strip()
    if getattr(a, "city_rel", None) and a.city_rel.name and a.city_rel.name.strip():
        return a.city_rel.name.strip()
    return "Unknown"


def _get_footer_cities(db: Session, limit: int = 16):
    rows = (
        db.query(Agency.city, func.count(Agency.registration_id).label("n"))
        .filter(Agency.city.isnot(None), Agency.city != "")
        .group_by(Agency.city)
        .order_by(func.count(Agency.registration_id).desc(), Agency.city.asc())
        .limit(limit)
        .all()
    )
    out = []
    for city, _cnt in rows:
        q = urllib.parse.quote(city)
        out.append(
            {
                "name": city,
                "operators_href": f"/city/{q}/umrah_operators",
                "packages_href": f"/city/{q}/umrah_packages",
            }
        )
    return out


def _get_footer_cities_cached(db: Session, *, limit: int = 16, ttl_seconds: int = 600):
    now = datetime.now(timezone.utc)
    if (
        _footer_cache["data"]
        and _footer_cache["limit"] == limit
        and now < _footer_cache["expires"]
    ):
        return _footer_cache["data"]
    data = _get_footer_cities(db, limit=limit)
    _footer_cache["data"] = data
    _footer_cache["limit"] = limit
    _footer_cache["expires"] = now + timedelta(seconds=ttl_seconds)
    return data


def _get_public_counts(db: Session) -> dict:
    """
    Count:
      - cities: distinct of coalesce(trim(Agency.city), City.name)
      - packages: total Package rows
      - agencies: total Agency rows
      - inquiries: total Inquiry rows (site-wide)
    """
    from app.db.models.package import Package as _Pkg
    from app.db.models.inquiry import Inquiry as _Inq

    canonical_city = func.lower(
        func.coalesce(
            func.nullif(func.trim(Agency.city), ""),
            func.trim(City.name),
        )
    )

    distinct_cities = (
        db.query(func.count(func.distinct(canonical_city)))
        .select_from(Agency)
        .outerjoin(City, City.id == Agency.city_id)
        .scalar()
    ) or 0

    packages = db.query(_Pkg.package_id).count()
    agencies = db.query(Agency.registration_id).count()
    inquiries = db.query(_Inq.inquiry_id).count()

    return {
        "cities": distinct_cities,
        "packages": packages or 0,
        "agencies": agencies or 0,
        "inquiries": inquiries or 0,
    }


def _resolve_active_agency_for_nav(request: Request, db: Session):
    """
    For navbar 'Dashboard' link:
      - If session has active agency and it's owned by the user, use it.
      - Else if the user owns exactly 1 agency, use that one.
      - Else None (navbar will point to /select-agency).
    """
    user = get_current_user_from_cookie(request, db)
    if not user:
        return None, None

    active_id = request.session.get("active_agency_id")
    if active_id:
        ag = (
            db.query(Agency)
            .filter(Agency.registration_id == active_id, Agency.user_id == user.id)
            .first()
        )
        if ag:
            return user, ag

    user_agencies = (
        db.query(Agency)
        .filter(Agency.user_id == user.id)
        .order_by(Agency.registration_id.desc())
        .all()
    )
    if len(user_agencies) == 1:
        return user, user_agencies[0]
    return user, None


def render(
    template_name: str,
    request: Request,
    db: Session,
    context: dict | None = None,
    *,
    is_public: bool = False,
):
    from app.web.deps import get_csrf_token

    ctx = dict(context or {})
    ctx["request"] = request
    ctx.setdefault("csrf_token", get_csrf_token(request))
    ctx["footer_cities"] = _get_footer_cities_cached(db, limit=16)

    # navbar context
    user, nav_agency = _resolve_active_agency_for_nav(request, db)
    ctx["user"] = user
    ctx["nav_agency"] = nav_agency
    ctx["is_admin"] = _is_admin_user(user)   # <<< add this

    ctx["metrics"] = _get_public_counts(db) if is_public else None
    return templates.TemplateResponse(template_name, ctx)




# ----------------- Auth -----------------

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if user:
        return redirect_after_login(request, db, user)
    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "auth/register.html",
        {"request": request, "flashes": flashes, "csrf_token": get_csrf_token(request)},
    )


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(""),
    last_name: str = Form(""),
    personal_email: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)

    if db.query(User).filter(User.email == email).first():
        flash(
            request,
            "The email address you are trying to register is already used for another account. "
            "Try registering with a different email address.",
            "error",
        )
        return RedirectResponse(url="/register", status_code=303)

    user = User(
        email=email,
        first_name=first_name or None,
        last_name=last_name or None,
        personal_email=personal_email or None,
        password_hash=hash_password(password),
        is_active=True,
        last_login_at=datetime.now(timezone.utc),
        is_email_verified=False,
        email_verified_at=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    ctx = new_otp_ctx(
        request,
        email=user.email,
        purpose="register",
        minutes=settings.OTP_EXP_MINUTES,
        user_id=user.id,
    )
    request.session["otp_ctx"] = ctx

    send_email_brevo(
        to_email=user.email,
        subject="Your verification code",
        html_content=(
            f"<p>Hi {user.first_name or ''} {user.last_name or ''},</p>"
            f"<p>Your verification code is: "
            f"<strong style='font-size:20px; letter-spacing:2px;'>{ctx['code']}</strong></p>"
            f"<p>This code will expire in {settings.OTP_EXP_MINUTES} minutes.</p>"
        ),
    )

    try:
        admin_email = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "amavia03@gmail.com")
        admin_html = f"""
        <div style="font-family: system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height:1.4;">
          <h3>New user registered</h3>
          <p><strong>Name:</strong> {(user.first_name or '') + (' ' + user.last_name if user.last_name else '')}</p>
          <p><strong>Email:</strong> {user.email}</p>
          <p><strong>Registered at:</strong> {user.last_login_at}</p>
          <p>Purpose: registration (OTP verification pending)</p>
        </div>
        """
        send_email_brevo(to_email=admin_email, subject="[Site] New user registered", html_content=admin_html)
    except Exception:
        pass

    flash(request, f"OTP sent to {user.email}. Please verify.", "info")
    return RedirectResponse(url="/verify", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if user:
        return redirect_after_login(request, db, user)
    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "flashes": flashes, "csrf_token": get_csrf_token(request)},
    )


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        flash(request, "Email not found or incorrect password", "error")
        return RedirectResponse(url="/login", status_code=303)

    if not getattr(user, "is_email_verified", False):
        ctx = new_otp_ctx(
            request,
            email=user.email,
            user_id=user.id,
            purpose="login",
            minutes=settings.OTP_EXP_MINUTES,
        )
        _send_login_otp(user.email, ctx["code"])
        flash(request, f"Verify your email to continue. We sent a code to {user.email}.", "info")
        return RedirectResponse(url="/verify", status_code=303)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    access = create_token(user.id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")

    resp = RedirectResponse(url="/post-login", status_code=303)
    set_access_cookie(resp, access)
    flash(request, "Login successful. Welcome back!", "success")
    return resp



@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    resp = RedirectResponse(url="/", status_code=303)
    clear_access_cookie(resp)
    request.session.pop("otp_ctx", None)
    return resp


@router.get("/verify", response_class=HTMLResponse)
def verify_page(request: Request, db: Session = Depends(get_db)):
    _ = pop_flashes(request)

    ctx = get_otp_ctx(request)
    otp_email = ctx.get("email") if ctx else None
    if not otp_email:
        u = get_current_user_from_cookie(request, db)
        if u:
            otp_email = u.email

    return templates.TemplateResponse(
        "auth/verify.html",
        {
            "request": request,
            "csrf_token": get_csrf_token(request),
            "otp_exp_minutes": settings.OTP_EXP_MINUTES,
            "otp_email": otp_email,
        },
    )


@router.post("/verify")
def verify_submit(
    request: Request,
    code: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)

    ok, err = check_code_and_update(request, code)
    if not ok:
        flash(request, err, "error")
        return RedirectResponse(url="/verify", status_code=303)

    user_id = request.session.pop("post_otp_user_id", None)
    if not user_id:
        flash(request, "Session lost user id. Please log in again.", "error")
        return RedirectResponse(url="/login", status_code=303)

    user = db.get(User, int(user_id))
    if not user:
        flash(request, "User not found. Please log in again.", "error")
        return RedirectResponse(url="/login", status_code=303)

    user.is_email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()

    access = create_token(user.id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")
    resp = RedirectResponse(url="/post-login", status_code=303)
    set_access_cookie(resp, access)
    flash(request, "OTP verified. Welcome!", "success")
    return resp



@router.post("/verify/resend")
def verify_resend(request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db)):
    require_csrf(request, csrf_token)

    ctx = get_otp_ctx(request)
    if not ctx:
        flash(request, "No OTP session. Please log in again.", "error")
        return RedirectResponse(url="/login", status_code=303)

    ctx = new_otp_ctx(
        request,
        email=ctx["email"],
        user_id=ctx.get("user_id"),
        purpose=ctx.get("purpose", "login"),
        minutes=settings.OTP_EXP_MINUTES,
    )

    send_email_brevo(
        to_email=ctx["email"],
        subject="Your OTP code (resend)",
        html_content=f"<p>Your new code:</p><h2 style='letter-spacing:3px;'>{ctx['code']}</h2>"
                     f"<p>It expires in {settings.OTP_EXP_MINUTES} minutes.</p>",
    )
    flash(request, "We sent a new code.", "success")
    return RedirectResponse(url="/verify", status_code=303)


# ----------------- Dashboard (protected) -----------------

@router.get("/agency/{registration_id}/dashboard", response_class=HTMLResponse)
def dashboard_agency(request: Request, registration_id: int, db: Session = Depends(get_db)):
    user = require_user(request, db)
    flashes = pop_flashes(request)

    set_active_agency(request, registration_id)

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == registration_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        set_active_agency(request, None)
        flash(request, "Agency not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    packages = db.query(Package).filter(Package.registration_id == registration_id).all()

    return templates.TemplateResponse(
        "dashboard_agency.html",
        {
            "request": request,
            "title": f"{agency.agencies_name} • Dashboard",
            "user": user,
            "flashes": flashes,
            "agency": agency,
            "packages": packages,
            "csrf_token": get_csrf_token(request),
        },
    )


# ----------------- Inquiries (protected) -----------------

@router.get("/inquiries", response_class=HTMLResponse)
def inquiries_list(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    flashes = pop_flashes(request)

    active_id = get_active_agency_id(request)
    if not active_id:
        return redirect_after_login(request, db, user)

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == active_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        set_active_agency(request, None)
        return redirect_after_login(request, db, user)

    inquiries = (
        db.query(Inquiry)
        .filter(Inquiry.registration_id == agency.registration_id)
        .order_by(Inquiry.inquiry_id.desc())
        .all()
    )

    return templates.TemplateResponse(
        "inquiries/list.html",
        {
            "request": request,
            "title": "Inquiries",
            "user": user,
            "flashes": flashes,
            "agency": agency,
            "inquiries": inquiries,
        },
    )


@router.get("/inquiries/{inquiry_id}", response_class=HTMLResponse)
def inquiries_detail(inquiry_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    flashes = pop_flashes(request)

    active_id = get_active_agency_id(request)
    if not active_id:
        return redirect_after_login(request, db, user)

    q = db.query(Inquiry).filter(Inquiry.inquiry_id == inquiry_id).first()
    if not q:
        flash(request, "Inquiry not found.", "error")
        return RedirectResponse(url="/inquiries", status_code=303)

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == q.registration_id, Agency.user_id == user.id)
        .first()
    )
    if not agency or agency.registration_id != active_id:
        flash(request, "Not allowed to view this inquiry.", "error")
        return RedirectResponse(url="/inquiries", status_code=303)

    try:
        if getattr(q, "viewed_at", None) is None:
            q.viewed_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        db.rollback()

    return templates.TemplateResponse(
        "inquiries/detail.html",
        {
            "request": request,
            "title": f"Inquiry • {q.name}",
            "user": user,
            "flashes": flashes,
            "agency": agency,
            "q": q,
        },
    )


@router.post("/inquiries/mark-all-seen")
def inquiries_mark_all_seen(request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db)):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    active_id = get_active_agency_id(request)
    if not active_id:
        return redirect_after_login(request, db, user)

    db.query(Inquiry).filter(
        Inquiry.registration_id == active_id,
        Inquiry.viewed_at.is_(None)
    ).update(
        {Inquiry.viewed_at: datetime.now(timezone.utc)}, synchronize_session=False
    )
    db.commit()
    flash(request, "All inquiries marked as seen.", "success")
    return RedirectResponse(url="/inquiries", status_code=303)


# ----------------- Select Agency (protected) -----------------

@router.get("/select-agency", response_class=HTMLResponse)
def select_agency_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    flashes = pop_flashes(request)
    agencies = (
        db.query(Agency)
        .filter(Agency.user_id == user.id)
        .order_by(Agency.agencies_name.asc())
        .all()
    )
    if not agencies:
        flash(
            request,
            "You don’t have any agencies yet. Create one to continue.",
            "info",
        )
        return RedirectResponse(url="/agency/new", status_code=303)

    return templates.TemplateResponse(
        "select_agency.html",
        {
            "request": request,
            "title": "Select Agency",
            "user": user,
            "flashes": flashes,
            "agencies": agencies,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/select-agency")
def select_agency_submit(
    request: Request,
    agency_id: int = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == agency_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        flash(request, "Agency not found or not yours.", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    set_active_agency(request, agency.registration_id)
    flash(request, f"Switched to: {agency.agencies_name}", "success")
    return RedirectResponse(
        url=f"/agency/{agency.registration_id}/dashboard",
        status_code=303,
    )


# ----------------- Agency CRUD (protected) -----------------

@router.get("/agency/new", response_class=HTMLResponse)
def agency_new_page(
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_user(request, db)

    existing = db.query(Agency).filter(Agency.user_id == user.id).count()
    if existing >= 1:
        flash(
            request,
            "You can only create one agency. Branches are supported.",
            "info",
        )
        return RedirectResponse(url="/upgrade-subscription", status_code=303)

    cities = db.query(City).order_by(City.name.asc()).all()
    current_year = date.today().year
    flashes = pop_flashes(request)

    agency_stub = {}
    branch_stub = {}

    return templates.TemplateResponse(
        "agency/new.html",
        {
            "request": request,
            "title": "Create Agency",
            "user": user,
            "flashes": flashes,
            "csrf_token": get_csrf_token(request),
            "cities": cities,
            "current_year": current_year,
            "agency": agency_stub,
            "branch": branch_stub,
        },
    )


@router.post("/agency/new")
def agency_new_submit(
    request: Request,
    agencies_name: str = Form(...),
    city: str = Form(...),
    country: str = Form(...),
    agency_email: str = Form(...),
    description: str = Form(""),
    public_registration_code: str = Form(""),
    website_url: str = Form(""),
    facebook_url: str = Form(""),
    instagram_url: str = Form(""),
    operating_since: str = Form(""),
    num_umrah_tours: str = Form(""),
    num_hajj_tours: str = Form(""),
    num_pilgrims_sent: str = Form(""),
    branch_name: str = Form(...),
    branch_address_line1: str = Form(""),
    branch_address_line2: str = Form(""),
    branch_contact_person: str = Form(""),
    branch_contact_number: str = Form(""),
    branch_is_main: Optional[str] = Form(None),
    # ✅ accept optional file as UploadFile via File()
    logo_file: Optional[UploadFile] = File(None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    # ---- tiny local helpers (no imports from routes_media to avoid ImportError) ----
    MEDIA_ROOT = Path("media").resolve()
    LOGO_NAME = "logo.webp"
    MAX_UPLOAD_BYTES = 5 * 1024 * 1024
    ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
    MAX_W, MAX_H = 2000, 2000

    def _agency_dir(registration_id: int) -> Path:
        return MEDIA_ROOT / "agency" / str(registration_id)

    def _logo_path(registration_id: int) -> Path:
        return _agency_dir(registration_id) / LOGO_NAME

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
    # -------------------------------------------------------------------------------

    def _to_int_or_none(s: str) -> Optional[int]:
        s = (s or "").strip()
        return int(s) if s.isdigit() else None

    if (not agencies_name.strip() or not city.strip()
            or not country.strip() or not agency_email.strip()):
        flash(request, "Agency name, city, country, and email are required.", "error")
        return RedirectResponse(url="/agency/new", status_code=303)
    if not branch_name.strip():
        flash(request, "Branch name is required.", "error")
        return RedirectResponse(url="/agency/new", status_code=303)

    city_name = city.strip()
    city_row = db.query(City).filter(City.name == city_name).first()
    if not city_row:
        city_row = City(name=city_name)
        db.add(city_row)
        db.commit()
        db.refresh(city_row)

    agency = Agency(
        agencies_name=agencies_name.strip(),
        city=city_name,
        country=country.strip(),
        description=_norm(description),
        public_registration_code=_norm(public_registration_code),
        website_url=_norm(website_url),
        facebook_url=_norm(facebook_url),
        instagram_url=_norm(instagram_url),
        agency_email=agency_email.strip(),
        operating_since=_to_int_or_none(operating_since),
        num_umrah_tours=_to_int_or_none(num_umrah_tours),
        num_hajj_tours=_to_int_or_none(num_hajj_tours),
        num_pilgrims_sent=_to_int_or_none(num_pilgrims_sent),
        city_id=city_row.id,
        user_id=user.id,
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)

    from app.db.models.agency_branch import AgencyBranch
    branch = AgencyBranch(
        agency_id=agency.registration_id,
        name=branch_name.strip(),
        address_line1=_norm(branch_address_line1),
        address_line2=_norm(branch_address_line2),
        city=agency.city,
        country=agency.country,
        contact_person=_norm(branch_contact_person),
        contact_number=_norm(branch_contact_number),
        is_main=True,
    )
    db.add(branch)

    if branch.city:
        agency.city = branch.city
    if branch.country:
        agency.country = branch.country

    db.commit()

    # ✅ Process logo (optional), identical behavior to Edit flow
    try:
        if logo_file is not None and getattr(logo_file, "filename", ""):
            if not (logo_file.content_type or "").startswith("image/"):
                raise HTTPException(status_code=400, detail="Upload must be an image file")

            raw = _read_limited(logo_file, MAX_UPLOAD_BYTES)
            webp_bytes = _validate_and_normalize_to_webp(raw)

            target_dir = _agency_dir(agency.registration_id)
            target_dir.mkdir(parents=True, exist_ok=True)

            tmp_path = target_dir / (LOGO_NAME + ".tmp")
            final_path = _logo_path(agency.registration_id)

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
            flash(request, "Logo uploaded successfully.", "success")
    except HTTPException as hx:
        flash(request, f"Logo upload skipped: {hx.detail}", "error")
    except Exception:
        flash(request, "Logo upload skipped due to an unexpected error.", "error")

    flash(request, "Agency and branch created!", "success")
    return RedirectResponse(
        url=f"/agency/{agency.registration_id}/dashboard",
        status_code=303,
    )



@router.get("/agency/{registration_id}/edit", response_class=HTMLResponse)
def agency_edit_page(
    request: Request,
    registration_id: int,
    db: Session = Depends(get_db),
):
    user = require_user(request, db)

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == registration_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        flash(request, "Agency not found or not yours.", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    cities = db.query(City).order_by(City.name.asc()).all()

    from app.db.models.agency_branch import AgencyBranch
    main_branch = (
        db.query(AgencyBranch)
        .filter(AgencyBranch.agency_id == agency.registration_id, AgencyBranch.is_main.is_(True))
        .first()
    )

    current_year = date.today().year

    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "agency/edit.html",
        {
            "request": request,
            "user": user,
            "agency": agency,
            "branch": main_branch,
            "cities": cities,
            "flashes": flashes,
            "csrf_token": get_csrf_token(request),
            "current_year": current_year,
        },
    )


@router.post("/agency/{registration_id}/edit")
def agency_edit_submit(
    request: Request,
    registration_id: int,
    agencies_name: str = Form(...),
    city: str = Form(...),
    country: str = Form(...),
    agency_email: str = Form(...),
    description: str = Form(""),
    public_registration_code: str = Form(""),
    website_url: str = Form(""),
    facebook_url: str = Form(""),
    instagram_url: str = Form(""),
    operating_since: str = Form(""),
    num_umrah_tours: str = Form(""),
    num_hajj_tours: str = Form(""),
    num_pilgrims_sent: str = Form(""),
    branch_name: str = Form(...),
    branch_address_line1: str = Form(""),
    branch_address_line2: str = Form(""),
    branch_contact_person: str = Form(""),
    branch_contact_number: str = Form(""),
    branch_is_main: Optional[str] = Form(None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    def _to_int_or_none(s: str) -> Optional[int]:
        s = (s or "").strip()
        return int(s) if s.isdigit() else None

    agency = db.query(Agency).filter(
        Agency.registration_id == registration_id,
        Agency.user_id == user.id,
    ).first()
    if not agency:
        flash(request, "Agency not found or not yours.", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    if not agencies_name.strip() or not city.strip() or not country.strip() or not agency_email.strip():
        flash(request, "Agency name, city, country, and email are required.", "error")
        return RedirectResponse(url=f"/agency/{registration_id}/edit", status_code=303)
    if not branch_name.strip():
        flash(request, "Branch name is required.", "error")
        return RedirectResponse(url=f"/agency/{registration_id}/edit", status_code=303)

    city_name = city.strip()
    city_row = db.query(City).filter(City.name == city_name).first()
    if not city_row:
        city_row = City(name=city_name)
        db.add(city_row)
        db.commit()
        db.refresh(city_row)

    agency.agencies_name = agencies_name.strip()
    agency.city = city_name
    agency.country = country.strip()
    agency.agency_email = agency_email.strip()
    agency.description = _norm(description)
    agency.public_registration_code = _norm(public_registration_code)
    agency.website_url = _norm(website_url)
    agency.facebook_url = _norm(facebook_url)
    agency.instagram_url = _norm(instagram_url)
    agency.operating_since = _to_int_or_none(operating_since)
    agency.num_umrah_tours = _to_int_or_none(num_umrah_tours)
    agency.num_hajj_tours = _to_int_or_none(num_hajj_tours)
    agency.num_pilgrims_sent = _to_int_or_none(num_pilgrims_sent)
    agency.city_id = city_row.id

    from app.db.models.agency_branch import AgencyBranch
    main_branch = db.query(AgencyBranch).filter(
        AgencyBranch.agency_id == agency.registration_id,
        AgencyBranch.is_main.is_(True),
    ).first()
    if not main_branch:
        main_branch = AgencyBranch(agency_id=agency.registration_id, is_main=True)
        db.add(main_branch)

    main_branch.name = branch_name.strip()
    main_branch.address_line1 = _norm(branch_address_line1)
    main_branch.address_line2 = _norm(branch_address_line2)
    main_branch.city = agency.city
    main_branch.country = agency.country
    main_branch.contact_person = _norm(branch_contact_person)
    main_branch.contact_number = _norm(branch_contact_number)
    main_branch.is_main = True

    if main_branch.city:
        agency.city = main_branch.city
    if main_branch.country:
        agency.country = main_branch.country

    db.commit()

    flash(request, "Agency updated.", "success")
    return RedirectResponse(
        url=f"/agency/{agency.registration_id}/dashboard",
        status_code=303,
    )


@router.post("/agency/{registration_id}/delete")
def agency_delete_submit(
    request: Request,
    registration_id: int,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)
    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == registration_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        flash(request, "Agency not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    db.query(Package).filter(Package.registration_id == registration_id).delete()
    db.delete(agency)
    db.commit()
    flash(request, "Agency deleted", "success")
    return RedirectResponse(url="/select-agency", status_code=303)


# ----------------- Packages (public + owner CRUD) -----------------

@router.get("/umrah_packages", response_class=HTMLResponse)
def packages_list(request: Request, db: Session = Depends(get_db)):
    from collections import defaultdict
    from sqlalchemy.orm import selectinload

    # Grab latest packages (unchanged)
    packages = db.query(Package).order_by(Package.package_id.desc()).all()
    
    reg_ids = {p.registration_id for p in packages}

    # Fetch agencies for those packages
    if reg_ids:
        agencies = (
            db.query(Agency)
            .options(selectinload(Agency.city_rel))
            .filter(Agency.registration_id.in_(reg_ids))
            .filter(Agency.is_blocked == False)
            .all()
        )
    else:
        agencies = []

    agency_by_id = {a.registration_id: a for a in agencies}

    # ✅ Only include packages whose agency exists AND is not blocked
    filtered_packages = [
        p for p in packages
        if (agency_by_id.get(p.registration_id) and not agency_by_id[p.registration_id].is_blocked)
    ]

    by_city: dict[str, list[Package]] = defaultdict(list)
    for p in filtered_packages:
        ag = agency_by_id.get(p.registration_id)
        city = _display_city(ag)
        by_city[city].append(p)
    
    if agency_by_id:
        packages = (
            db.query(Package)
            .filter(Package.registration_id.in_(agency_by_id.keys()))
            .order_by(Package.package_id.desc())
            .all()
        )
    def city_sort_key(name: str):
        return (name == "Unknown", name.casefold())

    packages_by_city = sorted(by_city.items(), key=lambda t: city_sort_key(t[0]))

    return render(
        "public/package_list.html",
        request,
        db,
        {
            "title": "Discover Packages",
            "packages_by_city": packages_by_city,
            "agency_by_id": agency_by_id,  # keeps agency info for cards
        },
        is_public=True,
    )

from sqlalchemy import func
from app.db.models.hotel import Hotel
from app.db.models.package_theme import PackageTheme


@router.get("/umrah_packages/{package_id}", response_class=HTMLResponse)
def package_detail(package_id: int, request: Request, db: Session = Depends(get_db)):
    pkg = (
        db.query(Package)
        .options(
            joinedload(Package.flights),
            joinedload(Package.stays),
            joinedload(Package.inclusion),
        )
        .filter(Package.package_id == package_id)
        .first()
    )
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == pkg.registration_id)
        .first()
    )
    if agency and agency.is_blocked:
        return templates.TemplateResponse(
            "void.html",
            _ctx(request, db, title="Access Restricted"),
            status_code=403,
        )

    # ---------- helpers ----------
    def _fmt_date(dt):
        if not dt:
            return None
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt)
            except Exception:
                return dt
        return dt.strftime("%d %b %Y")

    def _fmt_flight(f):
        if not f:
            return None
        date = getattr(f, "date", None) or getattr(f, "flight_date", None)
        ftype = getattr(f, "type", None) or getattr(f, "flight_type", None)
        via = getattr(f, "via", None) or getattr(f, "via_city", None)
        airline = getattr(f, "airline", None) or getattr(f, "airline_name", None)

        parts = []
        if date:
            parts.append(_fmt_date(date))
        if ftype:
            parts.append(str(ftype).title())
        if via:
            parts.append(f"via {via}")
        if airline:
            parts.append(airline)
        return " • ".join(parts) if parts else None

    def _fmt_dates(stay):
        if not stay:
            return None
        ci = getattr(stay, "check_in", None)
        co = getattr(stay, "check_out", None)
        if not ci and not co:
            return None
        if ci and co:
            return f"{_fmt_date(ci)} → {_fmt_date(co)}"
        return _fmt_date(ci or co)

    def _fmt_distance(stay, default_place):
        if not stay:
            return None
        text = (
            getattr(stay, "distance_text", None)
            or getattr(stay, "distance_label", None)
        )
        if text:
            return text
        meters = getattr(stay, "distance_m", None)
        if meters is not None:
            try:
                m = int(meters)
                return f"{m} m from {default_place}"
            except Exception:
                return f"{meters} from {default_place}"
        return None
    # -----------------------------

    flights_by_leg = {f.leg: f for f in (pkg.flights or [])}
    onward = flights_by_leg.get("onward")
    ret    = flights_by_leg.get("return")

    stays = {s.city: s for s in (pkg.stays or [])}
    mecca = stays.get("Mecca")
    med   = stays.get("Medinah")

    price_row = (
        db.query(PackagePrice)
        .filter(PackagePrice.package_id == pkg.package_id)
        .first()
    )

    # after you fetched raw theme from package_theme:
    raw_theme = (
        db.query(PackageTheme.theme_key)
        .filter(PackageTheme.package_id == package_id)
        .scalar()
        or "basic"
    )

    theme_key = normalize_theme_key(raw_theme)  # premium_aurora | premium | basic
    theme_template = f"package/themes/{theme_key}.html"

    onward_text = _fmt_flight(onward) or "—"
    return_text = _fmt_flight(ret) or "—"

    mecca_dates = _fmt_dates(mecca) or "—"
    med_dates   = _fmt_dates(med)   or "—"

    mecca_distance_label = _fmt_distance(mecca, "Haram") or "—"
    med_distance_label   = _fmt_distance(med, "Masjid an-Nabawi") or "—"

    # ---------- Resolve primary hotel IDs -> (name, link) map ----------
    hotel_ids = [s.hotel_id for s in (pkg.stays or []) if getattr(s, "hotel_id", None)]
    hotel_map = {}
    if hotel_ids:
        rows = (
            db.query(Hotel.id, Hotel.name, Hotel.link)
            .filter(Hotel.id.in_(hotel_ids))
            .all()
        )
        hotel_map = {r.id: {"name": r.name, "link": r.link} for r in rows}

    def resolved_hotel(stay):
        if not stay:
            return None, None
        name = stay.hotel_name or hotel_map.get(stay.hotel_id, {}).get("name")
        link = stay.hotel_link or hotel_map.get(stay.hotel_id, {}).get("link")
        return name, link

    mecca_hotel_name, mecca_hotel_link = resolved_hotel(mecca)
    med_hotel_name,   med_hotel_link   = resolved_hotel(med)

    # ---------- NEW: Resolve "or similar" hotels for both cities ----------
    def _get_similar_hotels(stay):
        """
        Read stay.similar_hotel_ids (e.g. '3,5,8') -> list[Hotel]
        Used only for display in themes (basic/premium/premium_aurora).
        """
        if not stay:
            return []
        raw_ids = getattr(stay, "similar_hotel_ids", None)
        if not raw_ids:
            return []
        try:
            ids = [int(x) for x in str(raw_ids).split(",") if x.strip().isdigit()]
        except Exception:
            return []
        if not ids:
            return []
        return (
            db.query(Hotel)
            .filter(Hotel.id.in_(ids))
            .order_by(Hotel.name.asc())
            .all()
        )

    mecca_similar_hotels = _get_similar_hotels(mecca)
    med_similar_hotels   = _get_similar_hotels(med)
    # --------------------------------------------------------------

    csrf_token = get_csrf_token(request)
    captcha_tag = f"pkg-inq:{pkg.package_id}"

    return render(
        "public/package_detail.html",
        request,
        db,
        {
            "title": pkg.package_name,
            "pkg": pkg,
            "agency": agency,

            "onward_text": onward_text,
            "return_text": return_text,

            "mecca_dates": mecca_dates,
            "med_dates":   med_dates,

            "mecca_distance_label": mecca_distance_label,
            "med_distance_label":   med_distance_label,

            "price_row": price_row,
            "theme_key": theme_key,
            "theme_template": theme_template,
            "theme_debug": f"raw={raw_theme} → {theme_key}",

            # primary hotels
            "mecca_hotel_name": mecca_hotel_name,
            "mecca_hotel_link": mecca_hotel_link,
            "med_hotel_name":   med_hotel_name,
            "med_hotel_link":   med_hotel_link,

            # ✅ NEW: lists used by basic / premium / premium_aurora templates
            "mecca_similar_hotels": mecca_similar_hotels,
            "med_similar_hotels":   med_similar_hotels,

            "csrf_token": csrf_token,
            "captcha_q": new_captcha(request, captcha_tag),
        },
        is_public=True,
    )

@router.post("/umrah_packages/{package_id}/inquire")
def package_inquire_submit(
    request: Request,
    package_id: int,
    name: str = Form(...),
    phone_number: str = Form(...),
    inquiry: str = Form(...),
    source: str = Form(""),
    website: str = Form(""),  # honeypot
    captcha_answer: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)

    if website.strip():  # honeypot
        flash(request, "Thanks! Your inquiry was sent.", "success")
        return RedirectResponse(url=f"/umrah_packages/{package_id}", status_code=303)

    pkg = db.query(Package).filter(Package.package_id == package_id).first()
    if not pkg:
        flash(request, "Package not found", "error")
        return RedirectResponse(url="/umrah_packages", status_code=303)

    name = (name or "").strip()
    msg = (inquiry or "").strip()
    src = (source or "").strip()[:20]
    phone_raw = (phone_number or "").strip()
    phone = normalize_phone(phone_raw)

    if not name or not msg:
        flash(request, "Please fill all required fields.", "error")
        return RedirectResponse(url=f"/umrah_packages/{package_id}", status_code=303)

    if not is_valid_phone(phone):
        flash(
            request,
            "Enter a valid phone number (e.g., +9198xxxxxxxx or a 10-digit Indian mobile starting 6–9).",
            "error",
        )
        return RedirectResponse(url=f"/umrah_packages/{package_id}", status_code=303)

    # unified tag with detail page
    if not check_captcha(request, tag=f"pkg-inq:{package_id}", user_answer=captcha_answer):
        flash(request, "CAPTCHA was incorrect. Please try again.", "error")
        new_captcha(request, tag=f"pkg-inq:{package_id}")
        return RedirectResponse(url=f"/umrah_packages/{package_id}", status_code=303)

    try:
        db.add(
            Inquiry(
                name=name,
                phone_number=phone,
                inquiry=msg,
                source=src or None,
                registration_id=pkg.registration_id,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        flash(request, "Could not save inquiry. Please try again.", "error")
        return RedirectResponse(url=f"/umrah_packages/{package_id}", status_code=303)

    flash(request, "Thanks! Your inquiry was sent.", "success")
    return RedirectResponse(url=f"/umrah_packages/{package_id}", status_code=303)


# ---- Owner: Package create/edit/delete (protected) ----

@router.get("/package/new", response_class=HTMLResponse)
def package_new_page(
    request: Request,
    agency_id: int = Query(...),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)

    from app.db.models.hotel import Hotel

    mecca_hotels = db.query(Hotel).filter(Hotel.city == "Mecca").order_by(Hotel.name.asc()).all()
    medinah_hotels = db.query(Hotel).filter(Hotel.city == "Medinah").order_by(Hotel.name.asc()).all()

    mecca_hotels_json = [{"id": h.id, "name": h.name} for h in mecca_hotels]
    medinah_hotels_json = [{"id": h.id, "name": h.name} for h in medinah_hotels]

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == agency_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        flash(request, "Agency not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    from app.db.models.hotel import Hotel
    mecca_hotels = (
        db.query(Hotel)
        .filter(Hotel.city == "Mecca")
        .order_by(Hotel.name.asc())
        .all()
    )
    medinah_hotels = (
        db.query(Hotel)
        .filter(Hotel.city == "Medinah")
        .order_by(Hotel.name.asc())
        .all()
    )

    from app.db.models.airline import Airline
    airlines = db.query(Airline).order_by(Airline.name.asc()).all()
    start = 2026
    end = max(date.today().year + 5, start + 5)
    years = list(range(start, end + 1))
    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "package/new.html",
        {
            "request": request,
            "title": "Add Package",
            "agency": agency,
            "flashes": flashes,
            "csrf_token": get_csrf_token(request),
            "mecca_hotels": mecca_hotels,      
            "medinah_hotels": medinah_hotels,
            "airlines": airlines,
            "years": years,
            "mecca_hotels": mecca_hotels,
            "medinah_hotels": medinah_hotels,
            "mecca_hotels_json": mecca_hotels_json,
            "medinah_hotels_json": medinah_hotels_json,
            },
    )

from app.db.models.package_airline import PackageAirline
@router.post("/package/new")
def package_new_submit(
    request: Request,
    agency_id: int = Form(...),
    package_type: str = Form(...),
    package_name: str = Form(...),
    days: int = Form(...),
    price: float = Form(...),
    description: str = Form(""),
    package_class: str = Form(""),
    travel_month: str = Form(""),
    travel_year: str = Form(""),

    airline_ids: Optional[List[int]] = Form(None),

    price_double: Optional[float] = Form(None),
    price_triple: Optional[float] = Form(None),
    price_quad: Optional[float] = Form(None),
    price_note: str = Form(""),

    onward_date: str = Form(""),
    onward_type: str = Form(""),
    onward_via: str = Form(""),
    onward_airline: str = Form(""),

    return_date: str = Form(""),
    return_type: str = Form(""),
    return_via: str = Form(""),
    return_airline: str = Form(""),

    mecca_check_in: str = Form(""),
    mecca_check_out: str = Form(""),
    mecca_hotel: str = Form(""),
    mecca_link: str = Form(""),
    mecca_distance_m: str = Form(""),
    mecca_distance_text: str = Form(""),

    med_check_in: str = Form(""),
    med_check_out: str = Form(""),
    med_hotel: str = Form(""),
    med_link: str = Form(""),
    med_distance_m: str = Form(""),
    med_distance_text: str = Form(""),
    mecca_similar: Optional[List[int]] = Form(None),
    medinah_similar: Optional[List[int]] = Form(None),

    incl_meals_enabled: Optional[str] = Form(None),
    incl_meals_desc: str = Form(""),
    incl_laundry_enabled: Optional[str] = Form(None),
    incl_laundry_desc: str = Form(""),
    incl_transport_enabled: Optional[str] = Form(None),
    incl_transport_desc: str = Form(""),
    incl_zamzam_enabled: Optional[str] = Form(None),
    incl_zamzam_desc: str = Form(""),
    incl_welcome_kit_enabled: Optional[str] = Form(None),
    incl_welcome_kit_desc: str = Form(""),
    incl_insurance_enabled: Optional[str] = Form(None),
    incl_insurance_desc: str = Form(""),
    incl_other: str = Form(""),

    csrf_token: str = Form(...),

    # THEME inputs
    detail_theme: str = Form("basic"),   # UI radio; if you also have a column, name it detail_theme (not 'theme')
    theme_key: str = Form("basic"),      # stored in package_theme table

    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)
    print("DEBUG mecca_similar:", mecca_similar)
    print("DEBUG medinah_similar:", medinah_similar)


    # ----- Validate agency ownership -----
    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == agency_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        flash(request, "Agency not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    # ----- Basic validations -----
    if not package_name.strip() or int(days) < 1:
        flash(request, "Please fill required fields correctly.", "error")
        return RedirectResponse(url=f"/package/new?agency_id={agency_id}", status_code=303)

    t_raw = (package_type or "").strip().lower()
    if t_raw not in {"haj", "umrah"}:
        flash(request, "Select package type: Haj or Umrah.", "error")
        return RedirectResponse(url=f"/package/new?agency_id={agency_id}", status_code=303)

    cls_raw = (package_class or "").strip().lower()
    allowed_cls = {"economy", "business", "first"}
    cls_val = cls_raw if cls_raw in allowed_cls else None
    if cls_raw and not cls_val:
        flash(request, "Invalid package class. Choose Economy, Business, or First Class.", "error")
        return RedirectResponse(url=f"/package/new?agency_id={agency_id}", status_code=303)

    def _to_int_or_none(s: str) -> Optional[int]:
        s = (s or "").strip()
        return int(s) if s.isdigit() else None

    tm = _to_int_or_none(travel_month)
    ty = _to_int_or_none(travel_year)
    if tm is not None and not (1 <= tm <= 12):
        flash(request, "Travel month must be between 1 and 12.", "error")
        return RedirectResponse(url=f"/package/new?agency_id={agency_id}", status_code=303)
    if ty is not None and ty < 2026:
        flash(request, "Travel year must be 2026 or later.", "error")
        return RedirectResponse(url=f"/package/new?agency_id={agency_id}", status_code=303)

    # Normalize selected theme text
    selected_theme = (detail_theme or theme_key or "basic").strip() or "basic"

    # ----------------------------------------------------------------------
    # 1) Create Package  (IMPORTANT: do NOT pass theme=... here)
    # ----------------------------------------------------------------------
    pkg = Package(
        registration_id=agency.registration_id,
        package_type=t_raw,
        package_name=package_name.strip(),
        package_class=cls_val,
        days=int(days),
        price=price,
        description=_norm(description),
        travel_month=tm,
        travel_year=ty,
        # DO NOT set theme=... here — it collides with relationship named "theme"
    )
    db.add(pkg)
    db.flush()  # ensures pkg.package_id is available

    # If you added a separate text column like `detail_theme` on packages, set it safely:
    try:
        # This will work only if a simple column named detail_theme exists.
        setattr(pkg, "detail_theme", selected_theme)
    except Exception:
        # Ignore if column doesn't exist or is a hybrid/relationship
        pass

    # ----------------------------------------------------------------------
    # 2) Upsert into package_theme
    # ----------------------------------------------------------------------
    existing = db.get(PackageTheme, pkg.package_id)
    if existing:
        existing.theme_key = selected_theme
        existing.set_at = datetime.utcnow()
        # existing.set_by_user_id = user.id  # if you wire the FK later
    else:
        db.add(
            PackageTheme(
                package_id=pkg.package_id,
                theme_key=selected_theme,
                set_by_user_id=None,  # or user.id if you wire it
            )
        )

    # ----------------------------------------------------------------------
    # 3) Airlines junction
    # ----------------------------------------------------------------------
    if airline_ids:
        unique_airline_ids = sorted({int(aid) for aid in airline_ids if str(aid).isdigit()})
        for aid in unique_airline_ids:
            db.add(PackageAirline(package_id=pkg.package_id, airline_id=aid))

    # ----------------------------------------------------------------------
    # 4) Variant prices
    # ----------------------------------------------------------------------
    if any(v is not None for v in (price_double, price_triple, price_quad)) or (price_note and price_note.strip()):
        db.add(
            PackagePrice(
                package_id=pkg.package_id,
                price_double=price_double,
                price_triple=price_triple,
                price_quad=price_quad,
                note=(price_note or "").strip() or None,
            )
        )

    # ----------------------------------------------------------------------
    # 5) Flights
    # ----------------------------------------------------------------------
    if any([onward_date, onward_type, onward_via, onward_airline]):
        db.add(
            PackageFlight(
                package_id=pkg.package_id,
                leg="onward",
                flight_date=_to_date(onward_date),
                flight_type=_norm(onward_type) if onward_type in ("direct", "via") else None,
                via_city=_norm(onward_via),
                airline_name=_norm(onward_airline),
            )
        )
    if any([return_date, return_type, return_via, return_airline]):
        db.add(
            PackageFlight(
                package_id=pkg.package_id,
                leg="return",
                flight_date=_to_date(return_date),
                flight_type=_norm(return_type) if return_type in ("direct", "via") else None,
                via_city=_norm(return_via),
                airline_name=_norm(return_airline),
            )
        )

    # ----------------------------------------------------------------------
    # 6) Stays
    # ----------------------------------------------------------------------
    from app.db.models.hotel import Hotel

    def resolve_hotel_and_distance(
        name_txt: str,
        link_txt: str,
        city: str,
        raw_distance_m: str,
        raw_distance_text: str,
    ) -> tuple[int | None, int | None, str | None]:
        """
        1. Find or create Hotel row by (name, city)
        2. If distance fields are empty, fill them from hotel.distance_km (if present)
        """
        name = (name_txt or "").strip()
        link = (link_txt or "").strip() or None
        distance_text = (raw_distance_text or "").strip()
        distance_m = None

        # parse distance_m from form if given
        raw_m = (raw_distance_m or "").strip()
        if raw_m.isdigit():
            distance_m = int(raw_m)

        # no hotel name -> nothing to resolve
        if not name:
            return None, distance_m or None, distance_text or None

        # 1) find existing hotel
        row = (
            db.query(Hotel)
            .filter(Hotel.name == name, Hotel.city == city)
            .first()
        )
        if row:
            # update link if we didn't have one before
            if link and not row.link:
                row.link = link
        else:
            # 2) create a new hotel if not found
            row = Hotel(name=name, city=city, link=link)
            db.add(row)
            db.flush()

        # 3) If no distance filled on form but hotel has distance_km, use it
        if distance_m is None and row.distance_km is not None:
            try:
                meters = int(float(row.distance_km) * 1000)
            except Exception:
                meters = None

            if meters is not None:
                distance_m = meters

                if not distance_text:
                    # simple default label
                    if city == "Mecca":
                        distance_text = f"{meters} m from Haram"
                    else:
                        distance_text = f"{meters} m from Masjid"

        return row.id, (distance_m or None), (distance_text or None)

    # ---- Mecca stay ----
    mecca_stay = None
    if any([mecca_check_in, mecca_check_out, mecca_hotel, mecca_link, mecca_distance_m, mecca_distance_text]):
        mecca_hotel_id, mecca_distance_m_val, mecca_distance_text_val = resolve_hotel_and_distance(
            mecca_hotel,
            mecca_link,
            "Mecca",
            mecca_distance_m,
            mecca_distance_text,
        )
        similar_ids = ",".join(map(str, mecca_similar)) if mecca_similar else None,
        mecca_stay = PackageStay(
            
            package_id=pkg.package_id,
            city="Mecca",
            check_in=_to_date(mecca_check_in),
            check_out=_to_date(mecca_check_out),
            hotel_name=_norm(mecca_hotel),
            hotel_link=_norm(mecca_link),
            distance_text=mecca_distance_text_val,
            distance_m=mecca_distance_m_val,
            hotel_id=mecca_hotel_id,
            similar_hotel_ids=similar_ids,
        )
        db.add(mecca_stay)


    # ---- Medinah stay ----
    med_stay = None
    if any([med_check_in, med_check_out, med_hotel, med_link, med_distance_m, med_distance_text]):
        med_hotel_id, med_distance_m_val, med_distance_text_val = resolve_hotel_and_distance(
            med_hotel,
            med_link,
            "Medinah",
            med_distance_m,
            med_distance_text,
        )
        similar_ids = ",".join(map(str, medinah_similar)) if medinah_similar else None
        med_stay = PackageStay(
            
            package_id=pkg.package_id,
            city="Medinah",
            check_in=_to_date(med_check_in),
            check_out=_to_date(med_check_out),
            hotel_name=_norm(med_hotel),
            hotel_link=_norm(med_link),
            distance_text=med_distance_text_val,
            distance_m=med_distance_m_val,
            hotel_id=med_hotel_id,
            similar_hotel_ids=similar_ids,
        )
        db.add(med_stay)

        # ----------------------------------------------------------------------
    # 7.5) Auto-compute "or similar" hotels for each stay
    # ----------------------------------------------------------------------
    if mecca_stay and mecca_stay.hotel_id:
        mecca_stay.similar_hotel_ids = find_similar_hotel_ids(
            db=db,
            base_hotel_id=mecca_stay.hotel_id,
            city="Mecca",
            limit=4,
        ) or None

    if med_stay and med_stay.hotel_id:
        med_stay.similar_hotel_ids = find_similar_hotel_ids(
            db=db,
            base_hotel_id=med_stay.hotel_id,
            city="Medinah",
            limit=4,
        ) or None



    # ----------------------------------------------------------------------
    # 7) Inclusions
    # ----------------------------------------------------------------------
    any_incl = any(
        [
            incl_meals_enabled,
            (incl_meals_desc or "").strip(),
            incl_laundry_enabled,
            (incl_laundry_desc or "").strip(),
            incl_transport_enabled,
            (incl_transport_desc or "").strip(),
            incl_zamzam_enabled,
            (incl_zamzam_desc or "").strip(),
            incl_welcome_kit_enabled,
            (incl_welcome_kit_desc or "").strip(),
            incl_insurance_enabled,
            (incl_insurance_desc or "").strip(),
            (incl_other or "").strip(),
        ]
    )
    if any_incl:
        db.add(
            PackageInclusion(
                package_id=pkg.package_id,
                meals_enabled=1 if incl_meals_enabled == "on" else 0,
                meals_desc=_norm(incl_meals_desc),
                laundry_enabled=1 if incl_laundry_enabled == "on" else 0,
                laundry_desc=_norm(incl_laundry_desc),
                transport_enabled=1 if incl_transport_enabled == "on" else 0,
                transport_desc=_norm(incl_transport_desc),
                zamzam_enabled=1 if incl_zamzam_enabled == "on" else 0,
                zamzam_desc=_norm(incl_zamzam_desc),
                welcome_kit_enabled=1 if incl_welcome_kit_enabled == "on" else 0,
                welcome_kit_desc=_norm(incl_welcome_kit_desc),
                insurance_enabled=1 if incl_insurance_enabled == "on" else 0,
                insurance_desc=_norm(incl_insurance_desc),
                other_notes=_norm(incl_other),
            )
        )

    db.commit()

    flash(request, "Package added! Let’s add the day-by-day itinerary (you can skip it).", "info")
    return RedirectResponse(url=f"/package/{pkg.package_id}/itinerary/wizard?day=1", status_code=303)



@router.get("/package/{package_id}/itinerary/wizard", response_class=HTMLResponse)
def itinerary_wizard_page(
    request: Request,
    package_id: int,
    day: int = Query(1),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)

    pkg = db.query(Package).filter(Package.package_id == package_id).first()
    if not pkg:
        flash(request, "Package not found", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == pkg.registration_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        flash(request, "Not allowed", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    total_days = max(int(pkg.days or 1), 1)
    current_day = min(max(int(day or 1), 1), total_days)

    entry = (
        db.query(PackageItinerary)
        .filter(PackageItinerary.package_id == package_id, PackageItinerary.day_number == current_day)
        .first()
    )
    notes = entry.notes if entry else ""

    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "package/itinerary_wizard.html",
        {
            "request": request,
            "title": f"Itinerary • Day {current_day} of {total_days}",
            "user": user,
            "agency": agency,
            "pkg": pkg,
            "current_day": current_day,
            "total_days": total_days,
            "notes": notes,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/package/{package_id}/itinerary/wizard")
def itinerary_wizard_submit(
    request: Request,
    package_id: int,
    csrf_token: str = Form(...),
    day_number: Optional[int] = Form(None),
    notes: Optional[List[str]] = Form(None, alias="notes[]"),
    nav: str = Form("next"),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    pkg = db.query(Package).filter(Package.package_id == package_id).first()
    if not pkg:
        flash(request, "Package not found", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == pkg.registration_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        flash(request, "Not allowed to edit this itinerary", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    total_days = pkg.days or 0

    try:
        if day_number is not None:
            submitted_text = (notes[0] if notes and len(notes) > 0 else "") if notes is not None else ""
            txt_norm = (submitted_text or "").strip() or None

            row = (
                db.query(PackageItinerary)
                .filter(PackageItinerary.package_id == pkg.package_id, PackageItinerary.day_number == int(day_number))
                .first()
            )
            if row:
                row.notes = txt_norm
            else:
                db.add(PackageItinerary(package_id=pkg.package_id, day_number=int(day_number), notes=txt_norm))

            db.commit()

            if nav == "back":
                prev_day = max(1, int(day_number) - 1)
                return RedirectResponse(url=f"/package/{pkg.package_id}/itinerary/wizard?day={prev_day}", status_code=303)
            elif nav == "next":
                next_day = min(total_days, int(day_number) + 1)
                return RedirectResponse(url=f"/package/{pkg.package_id}/itinerary/wizard?day={next_day}", status_code=303)
            else:
                flash(request, "Itinerary saved.", "success")
                return RedirectResponse(url=f"/agency/{agency.registration_id}/dashboard", status_code=303)

        else:
            notes_list = notes or []
            if len(notes_list) < total_days:
                notes_list = notes_list + [""] * (total_days - len(notes_list))
            elif len(notes_list) > total_days:
                notes_list = notes_list[:total_days]

            for idx, txt in enumerate(notes_list, start=1):
                txt_norm = (txt or "").strip() or None
                row = (
                    db.query(PackageItinerary)
                    .filter(PackageItinerary.package_id == pkg.package_id, PackageItinerary.day_number == idx)
                    .first()
                )
                if row:
                    row.notes = txt_norm
                else:
                    db.add(PackageItinerary(package_id=pkg.package_id, day_number=idx, notes=txt_norm))

            db.commit()
            flash(request, "Itinerary saved.", "success")
            return RedirectResponse(url=f"/agency/{agency.registration_id}/dashboard", status_code=303)

    except Exception as e:
        db.rollback()
        print("Error saving itinerary:", e)
        flash(request, "Could not save itinerary. Please try again.", "error")
        return RedirectResponse(url=f"/package/{pkg.package_id}/itinerary/wizard", status_code=303)


from datetime import date
from fastapi import Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

@router.get("/package/{package_id}/edit", response_class=HTMLResponse)
def package_edit_page(request: Request, package_id: int, db: Session = Depends(get_db)):
    user = require_user(request, db)

    pkg = db.query(Package).filter(Package.package_id == package_id).first()
    if not pkg:
        flash(request, "Package not found", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == pkg.registration_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        flash(request, "Not allowed to edit this package", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    onward = db.query(PackageFlight).filter(
        PackageFlight.package_id == pkg.package_id,
        PackageFlight.leg == "onward"
    ).first()

    ret = db.query(PackageFlight).filter(
        PackageFlight.package_id == pkg.package_id,
        PackageFlight.leg == "return"
    ).first()

    mecca = db.query(PackageStay).filter(
        PackageStay.package_id == pkg.package_id,
        PackageStay.city == "Mecca"
    ).first()

    med = db.query(PackageStay).filter(
        PackageStay.package_id == pkg.package_id,
        PackageStay.city == "Medinah"
    ).first()

    incl = db.query(PackageInclusion).filter(
        PackageInclusion.package_id == pkg.package_id
    ).first()

    price_row = db.query(PackagePrice).filter(
        PackagePrice.package_id == pkg.package_id
    ).first()

    # ✅ hotels split by city for dropdowns
    from app.db.models.hotel import Hotel
    mecca_hotels = db.query(Hotel).filter(Hotel.city == "Mecca").order_by(Hotel.name.asc()).all()
    medinah_hotels = db.query(Hotel).filter(Hotel.city == "Medinah").order_by(Hotel.name.asc()).all()

    # If anything else still needs "all hotels", keep it (safe)
    hotels = db.query(Hotel).order_by(Hotel.name.asc()).all()

    from app.db.models.airline import Airline
    airlines = db.query(Airline).order_by(Airline.name.asc()).all()

    selected_airline_ids = {pa.airline_id for pa in pkg.package_airlines}

    start = 2026
    end = max(date.today().year + 5, start + 5)
    years = list(range(start, end + 1))

    flashes = pop_flashes(request)

    return templates.TemplateResponse(
        "package/edit.html",
        {
            "request": request,
            "title": "Edit Package",
            "user": user,
            "flashes": flashes,
            "agency": agency,
            "pkg": pkg,
            "onward": onward,
            "ret": ret,
            "mecca": mecca,
            "med": med,
            "incl": incl,
            "price_row": price_row,
            "csrf_token": get_csrf_token(request),

            # ✅ new vars used by edit.html
            "mecca_hotels": mecca_hotels,
            "medinah_hotels": medinah_hotels,

            # keep old ones
            "hotels": hotels,
            "airlines": airlines,
            "selected_airline_ids": selected_airline_ids,
            "years": years,
        },
    )


@router.post("/package/{package_id}/edit")
def package_edit_submit(
    request: Request,
    package_id: int,
    package_type: str = Form(...),
    package_name: str = Form(...),
    days: int = Form(...),
    price: float = Form(...),
    description: str = Form(None),
    package_class: str = Form(""),
    travel_month: str = Form(""),
    travel_year: str = Form(""),
    airline_ids: Optional[List[int]] = Form(None),
    onward_date: str = Form(""),
    onward_type: str = Form(""),
    onward_via: str = Form(""),
    onward_airline: str = Form(""),
    return_date: str = Form(""),
    return_type: str = Form(""),
    return_via: str = Form(""),
    return_airline: str = Form(""),
    mecca_check_in: str = Form(""),
    mecca_check_out: str = Form(""),
    mecca_hotel: str = Form(""),
    mecca_link: str = Form(""),
    mecca_distance_m: str = Form(""),
    mecca_distance_text: str = Form(""),
    med_check_in: str = Form(""),
    med_check_out: str = Form(""),
    med_hotel: str = Form(""),
    med_link: str = Form(""),
    med_distance_m: str = Form(""),
    med_distance_text: str = Form(""),
    incl_meals_enabled: Optional[str] = Form(None),
    incl_meals_desc: str = Form(""),
    incl_laundry_enabled: Optional[str] = Form(None),
    incl_laundry_desc: str = Form(""),
    incl_transport_enabled: Optional[str] = Form(None),
    incl_transport_desc: str = Form(""),
    incl_zamzam_enabled: Optional[str] = Form(None),
    incl_zamzam_desc: str = Form(""),
    incl_welcome_kit_enabled: Optional[str] = Form(None),
    incl_welcome_kit_desc: str = Form(""),
    incl_insurance_enabled: Optional[str] = Form(None),
    incl_insurance_desc: str = Form(""),
    incl_other: str = Form(""),
    price_double: Optional[float] = Form(None),
    price_triple: Optional[float] = Form(None),
    price_quad: Optional[float] = Form(None),
    price_note: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    pkg = db.query(Package).filter(Package.package_id == package_id).first()
    if not pkg:
        flash(request, "Package not found", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == pkg.registration_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        flash(request, "Not allowed to edit this package", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    t_raw = (package_type or "").strip().lower()
    if t_raw not in {"haj", "umrah"}:
        flash(request, "Select package type: Haj or Umrah.", "error")
        return RedirectResponse(url=f"/package/{package_id}/edit", status_code=303)
    pkg.package_type = t_raw

    pkg.package_name = (package_name or "").strip()
    try:
        pkg.days = int(days)
    except Exception:
        pkg.days = days
    pkg.price = price
    pkg.description = (description or "").strip() or None

    cls_raw = (package_class or "").strip().lower()
    allowed_cls = {"economy", "business", "first"}
    pkg.package_class = cls_raw if cls_raw in allowed_cls else None
    if cls_raw and pkg.package_class is None:
        flash(request, "Invalid package class. Choose Economy, Business, or First Class.", "error")
        return RedirectResponse(url=f"/package/{package_id}/edit", status_code=303)

    def _to_int_or_none(s: str) -> Optional[int]:
        s = (s or "").strip()
        return int(s) if s.isdigit() else None

    tm = _to_int_or_none(travel_month)
    ty = _to_int_or_none(travel_year)
    if tm is not None and not (1 <= tm <= 12):
        flash(request, "Travel month must be between 1 and 12.", "error")
        return RedirectResponse(url=f"/package/{package_id}/edit", status_code=303)
    if ty is not None and ty < 2026:
        flash(request, "Travel year must be 2026 or later.", "error")
        return RedirectResponse(url=f"/package/{package_id}/edit", status_code=303)
    pkg.travel_month = tm
    pkg.travel_year = ty

    from app.db.models.package_airline import PackageAirline
    db.query(PackageAirline).filter(PackageAirline.package_id == pkg.package_id).delete(synchronize_session=False)
    if airline_ids:
        unique_airline_ids = sorted({int(aid) for aid in airline_ids if str(aid).isdigit()})
        for aid in unique_airline_ids:
            db.add(PackageAirline(package_id=pkg.package_id, airline_id=aid))

    onward = db.query(PackageFlight).filter_by(package_id=pkg.package_id, leg="onward").first()
    if any([onward_date, onward_type, onward_via, onward_airline]):
        if not onward:
            onward = PackageFlight(package_id=pkg.package_id, leg="onward")
            db.add(onward)
        onward.flight_date = _to_date(onward_date)
        onward.flight_type = _norm(onward_type) if onward_type in ("direct", "via") else None
        onward.via_city = _norm(onward_via)
        onward.airline_name = _norm(onward_airline)
    elif onward:
        db.delete(onward)

    ret = db.query(PackageFlight).filter_by(package_id=pkg.package_id, leg="return").first()
    if any([return_date, return_type, return_via, return_airline]):
        if not ret:
            ret = PackageFlight(package_id=pkg.package_id, leg="return")
            db.add(ret)
        ret.flight_date = _to_date(return_date)
        ret.flight_type = _norm(return_type) if return_type in ("direct", "via") else None
        ret.via_city = _norm(return_via)
        ret.airline_name = _norm(return_airline)
    elif ret:
        db.delete(ret)

    def resolve_hotel_id_by_name(
        name_txt: str,
        link_txt: str,
        city: str,
    ) -> int | None:
        """
        Used by EDIT package flow.
        Ensures the hotel exists with the correct city and returns its id.
        """
        name = (name_txt or "").strip()
        city = (city or "").strip()

        if not name or not city:
            return None

        row = get_or_create_hotel(
            db,
            name=name,
            city=city,
            link=(link_txt or "").strip() or None,
        )
        return row.id if row else None

    def upsert_stay(
            which_city: str,
            ci: str,
            co: str,
            hotel_name_txt: str,
            hotel_link_txt: str,
            dist_m: str,
            dist_txt: str,
        ):
            stay = (
                db.query(PackageStay)
                .filter_by(package_id=pkg.package_id, city=which_city)
                .first()
            )

            if any([ci, co, hotel_name_txt, hotel_link_txt, dist_m, dist_txt]):
                if not stay:
                    stay = PackageStay(package_id=pkg.package_id, city=which_city)
                    db.add(stay)

                stay.check_in = _to_date(ci)
                stay.check_out = _to_date(co)
                stay.hotel_name = _norm(hotel_name_txt)
                stay.hotel_link = _norm(hotel_link_txt)
                stay.distance_text = _norm(dist_txt)
                stay.distance_m = int(dist_m) if (dist_m and dist_m.strip().isdigit()) else None

                # 🔴 THIS was the missing city earlier
                stay.hotel_id = resolve_hotel_id_by_name(
                    hotel_name_txt,
                    hotel_link_txt,
                    which_city,   # "Mecca" or "Medinah"
                )
            elif stay:
                db.delete(stay)


    upsert_stay(
        "Mecca",
        mecca_check_in,
        mecca_check_out,
        mecca_hotel,
        mecca_link,
        mecca_distance_m,
        mecca_distance_text,
    )

    upsert_stay(
        "Medinah",
        med_check_in,
        med_check_out,
        med_hotel,
        med_link,
        med_distance_m,
        med_distance_text,
    )

    incl = db.query(PackageInclusion).filter_by(package_id=pkg.package_id).first()
    any_incl = any(
        [
            incl_meals_enabled, (incl_meals_desc or "").strip(),
            incl_laundry_enabled, (incl_laundry_desc or "").strip(),
            incl_transport_enabled, (incl_transport_desc or "").strip(),
            incl_zamzam_enabled, (incl_zamzam_desc or "").strip(),
            incl_welcome_kit_enabled, (incl_welcome_kit_desc or "").strip(),
            incl_insurance_enabled, (incl_insurance_desc or "").strip(),
            (incl_other or "").strip(),
        ]
    )
    if any_incl:
        if not incl:
            incl = PackageInclusion(package_id=pkg.package_id)
            db.add(incl)
        incl.meals_enabled = 1 if incl_meals_enabled == "on" else 0
        incl.meals_desc = _norm(incl_meals_desc)
        incl.laundry_enabled = 1 if incl_laundry_enabled == "on" else 0
        incl.laundry_desc = _norm(incl_laundry_desc)
        incl.transport_enabled = 1 if incl_transport_enabled == "on" else 0
        incl.transport_desc = _norm(incl_transport_desc)
        incl.zamzam_enabled = 1 if incl_zamzam_enabled == "on" else 0
        incl.zamzam_desc = _norm(incl_zamzam_desc)
        incl.welcome_kit_enabled = 1 if incl_welcome_kit_enabled == "on" else 0
        incl.welcome_kit_desc = _norm(incl_welcome_kit_desc)
        incl.insurance_enabled = 1 if incl_insurance_enabled == "on" else 0
        incl.insurance_desc = _norm(incl_insurance_desc)
        incl.other_notes = _norm(incl_other)
    elif incl:
        db.delete(incl)

    price_row = db.query(PackagePrice).filter(PackagePrice.package_id == pkg.package_id).first()
    if price_row:
        price_row.price_double = price_double
        price_row.price_triple = price_triple
        price_row.price_quad = price_quad
        price_row.note = (price_note or "").strip() or None
    else:
        if any(v is not None for v in (price_double, price_triple, price_quad)) or (price_note and price_note.strip()):
            db.add(
                PackagePrice(
                    package_id=pkg.package_id,
                    price_double=price_double,
                    price_triple=price_triple,
                    price_quad=price_quad,
                    note=(price_note or "").strip() or None,
                )
            )

    db.commit()
    flash(request, "Package updated", "success")
    return RedirectResponse(url=f"/agency/{agency.registration_id}/dashboard", status_code=303)

def find_similar_hotel_ids(
    db: Session,
    base_hotel_id: Optional[int],
    city: str,
    limit: int = 4,
) -> str:
    """
    Given a base hotel_id and city, return a comma-separated string of
    similar hotel IDs in that city.

    Similarity rules (simple, but effective):
      - Same city
      - Exclude the base hotel itself
      - Prefer same rating (±1 star)
      - Prefer closest distance_km
    """
    if not base_hotel_id:
        return ""

    base = db.query(Hotel).get(base_hotel_id)
    if not base:
        return ""

    q = db.query(Hotel).filter(
        Hotel.city == city,
        Hotel.id != base.id,
    )

    # If base has rating, stay within ±1 star
    if base.rating is not None:
        q = q.filter(
            Hotel.rating >= base.rating - 1,
            Hotel.rating <= base.rating + 1,
        )

    # Order by distance difference when we have distance_km
    if base.distance_km is not None:
        q = q.filter(Hotel.distance_km != None)  # noqa: E711
        q = q.order_by(func.abs(Hotel.distance_km - base.distance_km))
    else:
        # Fallback: just order by id
        q = q.order_by(Hotel.id.asc())

    similar = q.limit(limit).all()
    ids = [str(h.id) for h in similar]
    return ",".join(ids)


@router.post("/package/{package_id}/delete")
def package_delete(
    package_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)
    pkg = db.query(Package).filter(Package.package_id == package_id).first()
    if not pkg:
        flash(request, "Package not found", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    agency = db.query(Agency).filter(
        Agency.registration_id == pkg.registration_id, Agency.user_id == user.id
    ).first()
    if not agency:
        flash(request, "Package not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    db.delete(pkg)
    db.commit()
    flash(request, "Package deleted", "success")
    return RedirectResponse(
        url=f"/agency/{agency.registration_id}/dashboard",
        status_code=303,
    )


# ----------------- Operators (public) -----------------
from sqlalchemy.orm import selectinload
@router.get("/umrah_operators", response_class=HTMLResponse)
def operators_list(request: Request, db: Session = Depends(get_db)):
    agencies = (
        db.query(Agency)
        .options(selectinload(Agency.city_rel))
        .order_by(Agency.agencies_name.asc())
        .filter(Agency.is_blocked == False)
        .all()
    )
    grouped: dict[str, list[Agency]] = {}
    for a in agencies:
        grouped.setdefault(_display_city(a), []).append(a)
    for items in grouped.values():
        items.sort(key=lambda ag: (ag.agencies_name or "").casefold())

    def city_sort_key(name: str):
        return (name == "Unknown", name.casefold())

    cities = [{"city": name, "agencies": grouped[name]} for name in sorted(grouped, key=city_sort_key)]

    by_city = defaultdict(list)
    for a in agencies:
        city = _display_city(a)
        by_city[city].append(a)
    cards = [(city, len(items)) for city, items in by_city.items() if len(items) > 0]
    cards.sort(key=lambda t: (t[0] == "Unknown", t[0].casefold()))
    return render(
        "public/operators_list.html",
        request,
        db,
        {
            "title": "All Operators by City",
            "cities": cities,
            "total": len(agencies),
            "version": "operators_list v5",
        },
        is_public=True,
    )

from app.db.models.agency_branch import AgencyBranch

@router.get("/umrah_operators/{registration_id}", response_class=HTMLResponse)
def operator_detail(
    registration_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    # Always fetch THIS operator by registration_id (works for logged-in and anonymous users)
    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == registration_id)
        .first()
    )
    if not agency:
        raise HTTPException(status_code=404, detail="Operator not found")
    
    if getattr(agency, "is_blocked", False):
        flashes = pop_flashes(request)
        return templates.TemplateResponse(
            "void.html",
            {
                "request": request,
                "title": "Agency Blocked",
                "flashes": flashes,
                "csrf_token": get_csrf_token(request),
            },
        )

    # Packages belonging to this operator
    packages = (
        db.query(Package)
        .filter(Package.registration_id == registration_id)
        .order_by(Package.package_id.desc())
        .all()
    )

    # Optional: fetch the operator’s main branch (if exists) for address/contact details
    branch = (
        db.query(AgencyBranch)
        .filter(AgencyBranch.agency_id == registration_id, AgencyBranch.is_main == True)
        .first()
    )

    # Build UI helpers
    display_city = _display_city(agency)
    back_href = (
        f"/city/{urllib.parse.quote(display_city)}/umrah_operators"
        if display_city != "Unknown"
        else "/umrah_operators"
    )

    # Render strictly with this operator's data
    return render(
        "public/operator_detail.html",
        request,
        db,
        {
            "title": f"{agency.agencies_name} - Umrah Operator",
            "agency": agency,
            "packages": packages,
            "display_city": display_city,
            "back_href": back_href,
            "branch": branch,  # your template can show it if present
        },
        is_public=True,
    )





@router.get("/city/{city_name}/umrah_operators", response_class=HTMLResponse, name="city_operators")
def city_operators(city_name: str, request: Request, db: Session = Depends(get_db)):
    city = _decode_city(city_name)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    agencies = (
        db.query(Agency)
        .outerjoin(City, City.id == Agency.city_id)
        .options(selectinload(Agency.city_rel))
        .filter(
            func.lower(
                func.coalesce(
                    func.nullif(func.trim(Agency.city), ""),
                    func.trim(City.name),
                )
            )
            == city.lower().strip()
        )
        .filter(Agency.city == city, Agency.is_blocked == False)
        .order_by(Agency.agencies_name.asc())
        .all()
    )
    return render(
        "public/operators_by_city.html",
        request,
        db,
        {"title": f"Operators in {city}", "city": city, "agencies": agencies, "count": len(agencies)},
        is_public=True,
    )


@router.get("/city/{city_name}/umrah_packages", response_class=HTMLResponse, name="city_packages")
def city_packages(city_name: str, request: Request, db: Session = Depends(get_db)):
    city = _decode_city(city_name)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    rows = (
        db.query(Package, Agency)
        .join(Agency, Agency.registration_id == Package.registration_id)
        .outerjoin(City, City.id == Agency.city_id)
        .options(selectinload(Agency.city_rel))
        .filter(
            func.lower(
                func.coalesce(
                    func.nullif(func.trim(Agency.city), ""),
                    func.trim(City.name),
                )
            )
            == city.lower().strip()
        )
        .order_by(Package.package_id.desc())
        .all()
    )
    packages = [r[0] for r in rows]
    agencies = [r[1] for r in rows]
    agency_by_id = {a.registration_id: a for a in agencies}

    return render(
        "public/packages_city.html",
        request,
        db,
        {
            "title": f"Packages in {city}",
            "city": city,
            "packages": packages,
            "agency_by_id": agency_by_id,
            "count": len(packages),
        },
        is_public=True,
    )


@router.get("/city/{city_name}", response_class=HTMLResponse, name="city_hub")
def city_hub(city_name: str, request: Request, db: Session = Depends(get_db)):
    city = _decode_city(city_name)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    agencies = (
        db.query(Agency)
        .outerjoin(City, City.id == Agency.city_id)
        .options(selectinload(Agency.city_rel))
        .filter(
            func.lower(
                func.coalesce(
                    func.nullif(func.trim(Agency.city), ""),
                    func.trim(City.name),
                )
            )
            == city.lower().strip()
        )
        .filter(Agency.city == city, Agency.is_blocked == False)
        .order_by(Agency.agencies_name.asc())
        .all()
    )
    pkg_rows = (
        db.query(Package, Agency)
        .join(Agency, Agency.registration_id == Package.registration_id)
        .outerjoin(City, City.id == Agency.city_id)
        .filter(
            func.lower(
                func.coalesce(
                    func.nullif(func.trim(Agency.city), ""),
                    func.trim(City.name),
                )
            )
            == city.lower().strip()
        )
        .filter(Agency.is_blocked == False)
        .order_by(Package.package_id.desc())
        .all()
    )
    packages = [r[0] for r in pkg_rows]
    pkg_agencies = [r[1] for r in pkg_rows]
    agency_by_id = {a.registration_id: a for a in pkg_agencies}

    return render(
        "public/city_hub.html",
        request,
        db,
        {
            "title": f"{city} • Operators & Packages",
            "city": city,
            "agencies": agencies,
            "packages": packages,
            "agency_by_id": agency_by_id,
        },
        is_public=True,
    )


# ----------------- Legacy redirects -> Canonical -----------------

@router.get("/dashboard/agency/{registration_id}")
def legacy_dashboard_agency(registration_id: int):
    return RedirectResponse(url=f"/agency/{registration_id}/dashboard", status_code=308)


@router.get("/city/{city_name}/package")
def legacy_city_package(city_name: str):
    return RedirectResponse(url=f"/city/{urllib.parse.quote(city_name)}/umrah_packages", status_code=308)


@router.get("/umrah_packages/{city}/{package_id}")
def legacy_package_detail(city: str, package_id: int):
    return RedirectResponse(url=f"/umrah_packages/{package_id}", status_code=308)


@router.get("/umrah_operators/city/{city_name}")
def legacy_operators_city(city_name: str):
    return RedirectResponse(url=f"/city/{urllib.parse.quote(city_name)}/umrah_operators", status_code=308)


@router.get("/umrah_packages/city/{city_name}")
def legacy_packages_city(city_name: str):
    return RedirectResponse(url=f"/city/{urllib.parse.quote(city_name)}/umrah_packages", status_code=308)


# ----------------- Phone + CAPTCHA helpers -----------------

PHONE_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")  # +<country><nsn> (8–15 digits total)
PHONE_INDIA_RE = re.compile(r"^[6-9]\d{9}$")  # 10-digit Indian mobile


def normalize_phone(raw: str) -> str:
    """Keep digits and a single leading '+'. Convert leading '00' to '+'. Strip spaces/dashes."""
    s = re.sub(r"[^\d+]", "", (raw or ""))
    if s.startswith("00"):
        s = "+" + s[2:]
    s = s[0] + re.sub(r"\+", "", s[1:]) if s.startswith("+") else s
    return s


def is_valid_phone(s: str) -> bool:
    """Accept either E.164 (+XXXXXXXX) or 10-digit Indian mobile starting 6–9."""
    return bool(PHONE_E164_RE.fullmatch(s) or PHONE_INDIA_RE.fullmatch(s))


def new_captcha(request: Request, tag: str) -> str:
    """Create a simple math captcha and store the answer in session under a namespaced key."""
    a, b = random.randint(2, 9), random.randint(2, 9)
    request.session[f"captcha:{tag}"] = str(a + b)
    return f"{a} + {b} = ?"


def check_captcha(request: Request, tag: str, user_answer: str) -> bool:
    """Pop (invalidate) and compare the captcha answer."""
    key = f"captcha:{tag}"
    expected = request.session.pop(key, None)
    given = re.sub(r"\D", "", (user_answer or ""))
    return bool(expected) and (given == expected)


# ----------------- Debug -----------------

@router.get("/_debug/session")
def debug_session(request: Request):
    get_csrf_token(request)  # force-create
    return {"has_csrf": "csrf_token" in request.session, "keys": list(request.session.keys())}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_password_reset_token(db: Session, user_id: int, minutes: int = 60) -> str:
    """
    Create a plaintext token, store its SHA256 hash in DB with an aware UTC expiry,
    and return the plaintext token for emailing.
    """
    from app.db.models.password_reset_token import PasswordResetToken

    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    row = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(row)
    db.commit()
    db.refresh(row)
    return token


def verify_and_consume_token(db: Session, token: str):
    """
    Validate token: return (user, None) if valid and mark token used.
    Returns (None, error_message) on failure.
    """
    from app.db.models.password_reset_token import PasswordResetToken

    token_hash = _hash_token(token)
    prt = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    if not prt:
        return None, "Invalid or expired token."

    if prt.used:
        return None, "This reset link has already been used."

    now = datetime.now(timezone.utc)
    expires_at = prt.expires_at
    if expires_at is None:
        return None, "Invalid token (no expiry)."

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        return None, "This reset link has expired."

    prt.used = True
    db.commit()

    return prt.user, None


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {"request": request, "flashes": flashes, "csrf_token": get_csrf_token(request)},
    )


@router.post("/forgot-password")
def forgot_password_submit(
    request: Request,
    email: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)

    user = db.query(User).filter(User.email == email).first()
    if user:
        minutes = getattr(settings, "PASSWORD_RESET_EXP_MINUTES", 60)
        token = create_password_reset_token(db, user.id, minutes=minutes)
        reset_url = f"{settings.SITE_URL.rstrip('/')}/reset-password?token={token}&email={urllib.parse.quote(user.email)}"
        html = f"""
        <p>Hello {user.first_name or ''},</p>
        <p>We received a password reset request for your account. Click the link to reset your password (valid for {minutes} minutes):</p>
        <p><a href="{reset_url}">Reset password</a></p>
        <p>If you didn't request this, ignore this email.</p>
        """
        send_email_brevo(to_email=user.email, subject="Reset your password", html_content=html)

    flash(request, "If an account for this email exists, we sent a reset link.", "info")
    return RedirectResponse(url="/forgot-password", status_code=303)


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = Query(...), email: str | None = Query(None)):
    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "auth/reset_password.html",
        {"request": request, "csrf_token": get_csrf_token(request), "token": token, "email": email, "flashes": flashes},
    )


@router.post("/reset-password")
def reset_password_submit(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)

    if password != password2:
        flash(request, "Passwords do not match.", "error")
        return RedirectResponse(url=f"/reset-password?token={urllib.parse.quote(token)}", status_code=303)

    user, err = verify_and_consume_token(db, token)
    if err:
        flash(request, err, "error")
        return RedirectResponse(url="/forgot-password", status_code=303)

    try:
        user.password_hash = hash_password(password)
        db.commit()
    except Exception:
        db.rollback()
        flash(request, "Could not reset password. Try again.", "error")
        return RedirectResponse(url="/forgot-password", status_code=303)

    try:
        send_email_brevo(
            to_email=user.email,
            subject="Password changed",
            html_content=f"<p>Your password was changed. If you did not do this, contact support.</p>",
        )
    except Exception:
        pass

    flash(request, "Password reset. You can now login with your new password.", "success")
    return RedirectResponse(url="/login", status_code=303)


@router.get("/upgrade-subscription", response_class=HTMLResponse)
def upgrade_subscription(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)

    agencies = (
        db.query(Agency)
        .filter(Agency.user_id == user.id)
        .order_by(Agency.registration_id.desc())
        .all()
    )

    primary_id = agencies[0].registration_id if len(agencies) == 1 else None

    return templates.TemplateResponse(
        "upgrade_subscription.html",
        {
            "request": request,
            "title": "Upgrade Subscription",
            "user": user,
            "agencies": agencies,
            "primary_id": primary_id,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.get("/agency/{registration_id}/branches/new", response_class=HTMLResponse)
def branch_new_page(request: Request, registration_id: int, db: Session = Depends(get_db)):
    user = require_user(request, db)
    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == registration_id, Agency.user_id == user.id)
        .first()
    )
    if not agency:
        flash(request, "Agency not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "agency/branch_new.html",
        {
            "request": request,
            "title": "Add Branch",
            "agency": agency,
            "flashes": flashes,
            "csrf_token": get_csrf_token(request),
        },
    )


from app.db.models.agency_branch import AgencyBranch


@router.post("/agency/{registration_id}/branches/new")
def branch_new_submit(
    request: Request,
    registration_id: int,
    name: str = Form(...),
    address_line1: str = Form(""),
    address_line2: str = Form(""),
    city: str = Form(""),
    country: str = Form(""),
    contact_person: str = Form(""),
    contact_number: str = Form(""),
    is_main: Optional[str] = Form(None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    agency = db.query(Agency).filter(Agency.registration_id == registration_id, Agency.user_id == user.id).first()
    if not agency:
        flash(request, "Agency not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    if not name.strip():
        flash(request, "Branch name is required", "error")
        return RedirectResponse(url=f"/agency/{registration_id}/branches/new", status_code=303)

    existing_branches = db.query(AgencyBranch).filter(AgencyBranch.agency_id == agency.registration_id).all()
    make_main = True if not existing_branches else bool(is_main)

    if make_main and existing_branches:
        for b in existing_branches:
            if b.is_main:
                b.is_main = False

    branch = AgencyBranch(
        agency_id=agency.registration_id,
        name=name.strip(),
        address_line1=(address_line1 or "").strip() or None,
        address_line2=(address_line2 or "").strip() or None,
        city=(city or "").strip() or None,
        country=(country or "").strip() or None,
        contact_person=(contact_person or "").strip() or None,
        contact_number=(contact_number or "").strip() or None,
        is_main=make_main,
    )
    db.add(branch)

    if make_main:
        agency.city = (city or "").strip()
        agency.country = (country or "").strip()

    db.commit()

    flash(request, "Branch added.", "success")
    return RedirectResponse(url=f"/agency/{agency.registration_id}/dashboard", status_code=303)


# --- Hotels helper (no city) ---
from app.db.models.hotel import Hotel

def get_or_create_hotel(
    db,
    *,
    name: str,
    city: str,
    link: str | None = None,
    distance_km: float | None = None,
    rating: int | None = None,
) -> Hotel:
    """
    Find a hotel by (name, city). If it doesn't exist, create it.
    Also gently update missing fields (link/distance/rating) when we get new info.
    """
    name = (name or "").strip()
    city = (city or "").strip()

    if not name:
        raise ValueError("Hotel name is required")
    if not city:
        raise ValueError("Hotel city is required")

    row: Hotel | None = (
        db.query(Hotel)
        .filter(Hotel.name == name, Hotel.city == city)
        .first()
    )

    if row:
        updated = False

        if link and not row.link:
            row.link = link
            updated = True

        if distance_km is not None and row.distance_km is None:
            row.distance_km = distance_km
            updated = True

        if rating is not None and row.rating is None:
            row.rating = rating
            updated = True

        if updated:
            db.commit()
            db.refresh(row)

        return row

    # create new hotel
    row = Hotel(
        name=name,
        city=city,
        link=link,
        distance_km=distance_km,
        rating=rating,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

# --- Admin helpers ---
def _is_admin_email(email: str | None) -> bool:
    admins = {e.strip().lower() for e in getattr(settings, "ADMIN_EMAILS", [])}
    return bool(email and email.lower() in admins)

def _is_admin_user(user: User | None) -> bool:
    return bool(user) and (getattr(user, "is_admin", False) or _is_admin_email(user.email))
