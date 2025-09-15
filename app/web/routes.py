from datetime import timedelta, datetime, timezone
from collections import defaultdict
import urllib.parse
import re, random
from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from sqlalchemy import func

from app.core.config import settings
from app.core.deps import get_db
from app.core.security import hash_password, verify_password, create_token
from app.db.models.agency_detail import AgencyDetail
from app.db.models.agency_testimonial import AgencyTestimonial
from app.db.models.user import User
from app.db.models.agency import Agency
from app.db.models.package import Package
from app.db.models.package_flight import PackageFlight
from app.db.models.package_stay import PackageStay
from app.db.models.package_inclusion import PackageInclusion
from app.db.models.package_itinerary import PackageItinerary
from app.db.models.city import City
from app.db.models.inquiry import Inquiry
from app.db.models.agency_detail import AgencyDetail 
from app.web.deps import (
    COOKIE_NAME,
    get_current_user_from_cookie,
    require_user,
    flash,
    pop_flashes,
    get_csrf_token,
    require_csrf,
)

# OTP in session + Brevo email sender
from app.services.otp_session import new_otp_ctx, check_code_and_update, get_otp_ctx
from app.services.email_brevo import send_email_brevo

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")

from datetime import datetime, date

def _norm(s: str | None) -> str | None:
    s = (s or "").strip()
    return s or None

def _to_date(s: str | None) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    # Expecting HTML <input type="date"> → "YYYY-MM-DD"
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None

# ----------------- Helpers -----------------

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

def redirect_after_login(request: Request, db: Session, user: User) -> RedirectResponse:
    """Send the user to the right place after login/OTP."""
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
            url=f"/agency/{agencies[0].registration_id}/dashboard",  # NEW path
            status_code=303,
        )

    # multiple → force selection
    set_active_agency(request, None)
    return RedirectResponse(url="/select-agency", status_code=303)


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


# ----------------- Public: Home -----------------

@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    flashes = pop_flashes(request)

    # ---- Popular cities (unchanged) ----
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
            "operators_href": f"/city/{urllib.parse.quote(r[0])}/operators",
            "packages_href": f"/city/{urllib.parse.quote(r[0])}/packages",
            "hub_href":       f"/city/{urllib.parse.quote(r[0])}",
        }
        for r in rows
    ]

    # ---- NEW: resolve an agency to pass to the template ----
    active_agency = None
    if user:
        # 1) Prefer the agency selected in session (if any)
        active_id = get_active_agency_id(request)
        if active_id:
            active_agency = (
                db.query(Agency)
                .filter(Agency.registration_id == active_id, Agency.user_id == user.id)
                .first()
            )
        # 2) Fallback: if user owns exactly one agency, use it
        if not active_agency:
            user_agencies = (
                db.query(Agency)
                .filter(Agency.user_id == user.id)
                .order_by(Agency.registration_id.desc())
                .all()
            )
            if len(user_agencies) == 1:
                active_agency = user_agencies[0]

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "title": "Home",
            "user": user,
            "flashes": flashes,
            "popular_cities": popular_cities,
            # Always define 'agency' for the template to avoid UndefinedError
            "agency": active_agency,
        },
    )



# ----------------- Auth (register/login/verify/logout) -----------------

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if user:
        return redirect_after_login(request, db, user)
    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "auth/register.html",
        {"request": request, "flashes": flashes, "csrf_token": get_csrf_token(request)}
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
        flash(request, "Email already exists", "error")
        return RedirectResponse(url="/register", status_code=303)

    user = User(
        email=email,
        first_name=first_name or None,
        last_name=last_name or None,
        personal_email=personal_email or None,
        password_hash=hash_password(password),
        is_active=True,
        last_login_at=datetime.now(timezone.utc),
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
        {"request": request, "flashes": flashes, "csrf_token": get_csrf_token(request)}
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
        flash(request, "Invalid email or password", "error")
        return RedirectResponse(url="/login", status_code=303)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    ctx = new_otp_ctx(
        request,
        email=user.email,
        user_id=user.id,
        purpose="login",
        minutes=settings.OTP_EXP_MINUTES,
    )
    request.session["otp_ctx"] = ctx
    request.session["post_otp_user_id"] = user.id

    send_email_brevo(
        to_email=user.email,
        subject="Your OTP code",
        html_content=(
            f"<p>Your one-time code is:</p>"
            f"<h2 style='letter-spacing:3px;'>{ctx['code']}</h2>"
            f"<p>This code expires in {settings.OTP_EXP_MINUTES} minutes.</p>"
        ),
    )
    return RedirectResponse(url="/verify", status_code=303)

@router.post("/logout")
def logout(request: Request, csrf_token: str | None = Form(None)):
    resp = RedirectResponse(url="/", status_code=303)
    clear_access_cookie(resp)
    request.session.pop("otp_ctx", None)
    return resp

@router.get("/verify", response_class=HTMLResponse)
def verify_page(request: Request, db: Session = Depends(get_db)):
    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "auth/verify.html",
        {
            "request": request,
            "flashes": flashes,
            "csrf_token": get_csrf_token(request),
            "otp_exp_minutes": settings.OTP_EXP_MINUTES,
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

    access = create_token(user.id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")
    resp = redirect_after_login(request, db, user)
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
        flash(request, "You don’t have any agencies yet. Create one to continue.", "info")
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
def agency_new_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "agency/new.html",
        {"request": request, "user": user, "flashes": flashes, "csrf_token": get_csrf_token(request)}
    )

@router.post("/agency/new")
def agency_new_submit(
    request: Request,
    agencies_name: str = Form(...),
    country: str = Form(...),
    city: str = Form(...),
    description: str = Form(""),

    # details (no duplicate city/country asked)
    address_line1: str = Form(...),
    address_line2: str = Form(""),
    state:         str = Form(""),
    postal_code:   str = Form(""),
    contact1_name: str = Form(...),
    contact1_phone:str = Form(...),
    contact2_name: str = Form(""),
    contact2_phone:str = Form(""),
    website:       str = Form(""),

    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    # Validate core fields
    if not agencies_name.strip() or not country.strip() or not city.strip():
        flash(request, "All required fields must be filled", "error")
        return RedirectResponse(url="/agency/new", status_code=303)

    # Ensure city row
    city_row = db.query(City).filter(City.name == city.strip()).first()
    if not city_row:
        city_row = City(name=city.strip())
        db.add(city_row)
        db.commit()
        db.refresh(city_row)

    # Create Agency
    agency = Agency(
        agencies_name=agencies_name.strip(),
        country=country.strip(),
        city=city.strip(),
        description=(description or None),
        city_id=city_row.id,
        user_id=user.id,
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)

    def norm(s: str) -> str | None:
        s = (s or "").strip()
        return s or None

    # Create AgencyDetail — use agency.city/country directly (no duplicate inputs)
    detail = AgencyDetail(
        agency_id=agency.registration_id,
        address_line1=norm(address_line1),
        address_line2=norm(address_line2),
        city=agency.city,
        state=norm(state),
        country=agency.country,
        postal_code=norm(postal_code),
        website=norm(website),

        contact1_name=norm(contact1_name),
        contact1_phone=norm(contact1_phone),
        contact2_name=norm(contact2_name),
        contact2_phone=norm(contact2_phone),
    )
    db.add(detail)
    db.commit()

    flash(request, "Agency created!", "success")
    return RedirectResponse(
        url=f"/agency/{agency.registration_id}/dashboard",
        status_code=303,
    )


@router.get("/agency/{registration_id}/edit", response_class=HTMLResponse)
def agency_edit_page(request: Request, registration_id: int, db: Session = Depends(get_db)):
    user = require_user(request, db)
    agency = db.query(Agency).filter(
        Agency.registration_id == registration_id,
        Agency.user_id == user.id
    ).first()
    if not agency:
        flash(request, "Agency not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    detail = db.query(AgencyDetail).filter(AgencyDetail.agency_id == registration_id).first()

    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "agency/edit.html",
        {
            "request": request,
            "user": user,
            "flashes": flashes,
            "agency": agency,
            "detail": detail,  # <—
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/agency/{registration_id}/edit")
def agency_edit_submit(
    request: Request,
    registration_id: int,
    agencies_name: str = Form(...),
    country: str = Form(...),
    city: str = Form(...),
    description: str = Form(None),

    address_line1: str = Form(...),
    address_line2: str = Form(""),
    state:         str = Form(""),
    postal_code:   str = Form(""),
    contact1_name: str = Form(...),
    contact1_phone:str = Form(...),
    contact2_name: str = Form(""),
    contact2_phone:str = Form(""),
    website:       str = Form(""),

    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    agency = db.query(Agency).filter(
        Agency.registration_id == registration_id,
        Agency.user_id == user.id
    ).first()
    if not agency:
        flash(request, "Agency not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    # Update Agency
    city_row = db.query(City).filter(City.name == city.strip()).first()
    if not city_row:
        city_row = City(name=city.strip())
        db.add(city_row)
        db.commit()
        db.refresh(city_row)

    agency.agencies_name = agencies_name.strip()
    agency.country = country.strip()
    agency.city = city.strip()
    agency.description = (description or "").strip() or None
    agency.city_id = city_row.id

    def norm(s: str) -> str | None:
        s = (s or "").strip()
        return s or None

    # Upsert AgencyDetail (use agency.city/country to keep single source of truth)
    detail = db.query(AgencyDetail).filter(AgencyDetail.agency_id == registration_id).first()
    if not detail:
        detail = AgencyDetail(agency_id=registration_id)
        db.add(detail)

    detail.address_line1 = norm(address_line1)
    detail.address_line2 = norm(address_line2)
    detail.city          = agency.city
    detail.state         = norm(state)
    detail.country       = agency.country
    detail.postal_code   = norm(postal_code)
    detail.website       = norm(website)

    detail.contact1_name  = norm(contact1_name)
    detail.contact1_phone = norm(contact1_phone)
    detail.contact2_name  = norm(contact2_name)
    detail.contact2_phone = norm(contact2_phone)

    db.commit()
    flash(request, "Agency updated", "success")
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
    agency = db.query(Agency).filter(Agency.registration_id == registration_id, Agency.user_id == user.id).first()
    if not agency:
        flash(request, "Agency not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    # If your FK doesn't cascade, delete packages manually:
    db.query(Package).filter(Package.registration_id == registration_id).delete()
    db.delete(agency)
    db.commit()
    flash(request, "Agency deleted", "success")
    return RedirectResponse(url="/select-agency", status_code=303)


# ----------------- Packages (public + owner CRUD) -----------------

@router.get("/packages", response_class=HTMLResponse)
def packages_list(request: Request, db: Session = Depends(get_db)):
    packages = db.query(Package).order_by(Package.package_id.desc()).all()

    reg_ids = {p.registration_id for p in packages}
    agencies = (
        db.query(Agency)
        .filter(Agency.registration_id.in_(reg_ids) if reg_ids else False)
        .all()
    )
    agency_by_id = {a.registration_id: a for a in agencies}

    by_city = defaultdict(list)
    for p in packages:
        ag = agency_by_id.get(p.registration_id)
        city = (ag.city if ag and ag.city else "Unknown").strip()
        by_city[city].append(p)

    packages_by_city = sorted(by_city.items(), key=lambda t: t[0].lower())

    return templates.TemplateResponse(
        "public/package_list.html",  # make sure file name matches exactly
        {
            "request": request,
            "title": "Discover Packages",
            "packages_by_city": packages_by_city,
            "agency_by_id": agency_by_id,
        },
    )

@router.get("/packages/{package_id}", response_class=HTMLResponse)
def package_detail(package_id: int, request: Request, db: Session = Depends(get_db)):
    # Eager-load children to avoid extra queries
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

    agency = db.query(Agency).filter(Agency.registration_id == pkg.registration_id).first()

    # Organize children for easy template use
    flights_by_leg = {f.leg: f for f in (pkg.flights or [])}
    onward = flights_by_leg.get("onward")
    ret = flights_by_leg.get("return")

    mecca = next((s for s in (pkg.stays or []) if s.city == "Mecca"), None)
    med   = next((s for s in (pkg.stays or []) if s.city == "Medinah"), None)
    incl  = pkg.inclusion  # 1:1 or None
    captcha_q = new_captcha(request, tag=f"inq:{package_id}")

    return templates.TemplateResponse(
        "public/package_detail.html",
        {
            "request": request,
            "title": pkg.package_name,
            "pkg": pkg,
            "agency": agency,
            "csrf_token": get_csrf_token(request),
            "onward": onward,
            "ret": ret,
            "mecca": mecca,
            "med": med,
            "incl": incl,
            "captcha_q": captcha_q,
        },
    )
@router.post("/packages/{package_id}/inquire")
def package_inquire_submit(
    request: Request,
    package_id: int,
    name: str = Form(...),
    phone_number: str = Form(...),
    inquiry: str = Form(...),
    source: str = Form(""),
    website: str = Form(""),           # honeypot
    captcha_answer: str = Form(...),   # NEW
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)

    # Honeypot: if filled, pretend success
    if website.strip():
        flash(request, "Thanks! Your inquiry was sent.", "success")
        return RedirectResponse(url=f"/packages/{package_id}", status_code=303)

    pkg = db.query(Package).filter(Package.package_id == package_id).first()
    if not pkg:
        flash(request, "Package not found", "error")
        return RedirectResponse(url="/packages", status_code=303)

    # Normalize inputs
    name = (name or "").strip()
    msg  = (inquiry or "").strip()
    src  = (source or "").strip()[:20]
    phone_raw = (phone_number or "").strip()
    phone = normalize_phone(phone_raw)

    # Server-side validation
    if not name or not msg:
        flash(request, "Please fill all required fields.", "error")
        return RedirectResponse(url=f"/packages/{package_id}", status_code=303)

    if not is_valid_phone(phone):
        flash(
            request,
            "Enter a valid phone number (e.g., +9198xxxxxxxx or a 10-digit Indian mobile starting 6–9).",
            "error",
        )
        return RedirectResponse(url=f"/packages/{package_id}", status_code=303)

    # CAPTCHA check (namespaced per package)
    if not check_captcha(request, tag=f"inq:{package_id}", user_answer=captcha_answer):
        flash(request, "CAPTCHA was incorrect. Please try again.", "error")
        # regenerate a fresh captcha for the next view
        new_captcha(request, tag=f"inq:{package_id}")
        return RedirectResponse(url=f"/packages/{package_id}", status_code=303)

    # Save
    try:
        db.add(Inquiry(
            name=name,
            phone_number=phone,   # store normalized value
            inquiry=msg,
            source=src or None,
            registration_id=pkg.registration_id,
        ))
        db.commit()
    except Exception:
        db.rollback()
        flash(request, "Could not save inquiry. Please try again.", "error")
        return RedirectResponse(url=f"/packages/{package_id}", status_code=303)

    flash(request, "Thanks! Your inquiry was sent.", "success")
    return RedirectResponse(url=f"/packages/{package_id}", status_code=303)


# ---- Owner: Package create/edit/delete (protected) ----

@router.get("/package/new", response_class=HTMLResponse)
def package_new_page(request: Request, agency_id: int, db: Session = Depends(get_db)):
    user = require_user(request, db)
    agency = db.query(Agency).filter(Agency.registration_id == agency_id, Agency.user_id == user.id).first()
    if not agency:
        flash(request, "Agency not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "package/new.html",
        {"request": request, "user": user, "flashes": flashes, "agency": agency, "csrf_token": get_csrf_token(request)},
    )

@router.post("/package/new")
def package_new_submit(
    request: Request,
    agency_id: int = Form(...),
    package_name: str = Form(...),
    days: int = Form(...),
    price: float = Form(...),
    description: str = Form(""),

    # ---- Flights (optional) ----
    onward_date: str = Form(""),
    onward_type: str = Form(""),      # "direct" | "via"
    onward_via: str = Form(""),
    onward_airline: str = Form(""),

    return_date: str = Form(""),
    return_type: str = Form(""),
    return_via: str = Form(""),
    return_airline: str = Form(""),

    # ---- Stays (optional) ----
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

    # ---- Inclusions (optional) ----
    incl_meals: str = Form(""),
    incl_laundry: str = Form(""),
    incl_transport: str = Form(""),
    incl_other: str = Form(""),

    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    agency = db.query(Agency).filter(Agency.registration_id == agency_id, Agency.user_id == user.id).first()
    if not agency:
        flash(request, "Agency not found or not yours", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    pkg = Package(
        registration_id=agency.registration_id,
        package_name=package_name.strip(),
        days=days,
        price=price,
        description=_norm(description),
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)

    # ---- Flights (create if any field present) ----
    if any([onward_date, onward_type, onward_via, onward_airline]):
        db.add(PackageFlight(
            package_id=pkg.package_id,
            leg="onward",
            flight_date=_to_date(onward_date),
            flight_type=_norm(onward_type) if onward_type in ("direct", "via") else None,
            via_city=_norm(onward_via),
            airline_name=_norm(onward_airline),
        ))

    if any([return_date, return_type, return_via, return_airline]):
        db.add(PackageFlight(
            package_id=pkg.package_id,
            leg="return",
            flight_date=_to_date(return_date),
            flight_type=_norm(return_type) if return_type in ("direct", "via") else None,
            via_city=_norm(return_via),
            airline_name=_norm(return_airline),
        ))

    # ---- Stays ----
    if any([mecca_check_in, mecca_check_out, mecca_hotel, mecca_link, mecca_distance_m, mecca_distance_text]):
        db.add(PackageStay(
            package_id=pkg.package_id,
            city="Mecca",
            check_in=_to_date(mecca_check_in),
            check_out=_to_date(mecca_check_out),
            hotel_name=_norm(mecca_hotel),
            hotel_link=_norm(mecca_link),
            distance_text=_norm(mecca_distance_text),
            distance_m=int(mecca_distance_m) if mecca_distance_m.strip().isdigit() else None,
        ))

    if any([med_check_in, med_check_out, med_hotel, med_link, med_distance_m, med_distance_text]):
        db.add(PackageStay(
            package_id=pkg.package_id,
            city="Medinah",
            check_in=_to_date(med_check_in),
            check_out=_to_date(med_check_out),
            hotel_name=_norm(med_hotel),
            hotel_link=_norm(med_link),
            distance_text=_norm(med_distance_text),
            distance_m=int(med_distance_m) if med_distance_m.strip().isdigit() else None,
        ))

    # ---- Inclusions (1:1 create if any) ----
    if any([incl_meals, incl_laundry, incl_transport, incl_other]):
        db.add(PackageInclusion(
            package_id=pkg.package_id,
            meals=_norm(incl_meals),
            laundry=_norm(incl_laundry),
            transport=_norm(incl_transport),
            other_notes=_norm(incl_other),
        ))

    db.commit()
    flash(request, f"Package created. Let's add the itinerary ({days} day{'s' if days != 1 else ''}).", "info")
    return RedirectResponse(
        url=f"/package/{pkg.package_id}/itinerary/wizard?day=1",
        status_code=303,
    )

@router.get("/package/{package_id}/itinerary/wizard", response_class=HTMLResponse)
def itinerary_wizard_page(
    request: Request,
    package_id: int,
    day: int = Query(1),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)

    # Fetch package (must belong to the user)
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

    # Clamp day to [1, pkg.days]
    total_days = max(int(pkg.days or 1), 1)
    current_day = min(max(int(day or 1), 1), total_days)

    # Load existing note for this day (if any)
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
    day_number: int = Form(...),
    notes: str = Form(""),
    nav: str = Form("next"),  # 'next' | 'back' | 'skip' | 'finish'
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    # Load package and owning agency (must belong to logged-in user)
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
    current_day = min(max(int(day_number or 1), 1), total_days)

    # Upsert or delete (empty) the day's note
    text = (notes or "").strip()
    entry = (
        db.query(PackageItinerary)
        .filter(
            PackageItinerary.package_id == package_id,
            PackageItinerary.day_number == current_day
        )
        .first()
    )
    if text:
        if not entry:
            entry = PackageItinerary(package_id=package_id, day_number=current_day, notes=text)
            db.add(entry)
        else:
            entry.notes = text
    else:
        if entry:
            db.delete(entry)

    db.commit()

    # Keep session focused on this agency
    set_active_agency(request, agency.registration_id)

    # Navigation
    if nav == "back":
        prev_day = max(current_day - 1, 1)
        return RedirectResponse(url=f"/package/{package_id}/itinerary/wizard?day={prev_day}", status_code=303)

    if nav == "skip":
        next_day = current_day + 1
        if next_day > total_days:
            flash(request, "Itinerary saved.", "success")
            return RedirectResponse(url=f"/agency/{agency.registration_id}/dashboard", status_code=303)
        return RedirectResponse(url=f"/package/{package_id}/itinerary/wizard?day={next_day}", status_code=303)

    # Finish OR last day reached
    if nav == "finish" or current_day == total_days:
        flash(request, "Itinerary saved.", "success")
        return RedirectResponse(url=f"/agency/{agency.registration_id}/dashboard", status_code=303)

    # Default: Save & Next
    return RedirectResponse(url=f"/package/{package_id}/itinerary/wizard?day={current_day + 1}", status_code=303)

@router.get("/package/{package_id}/edit", response_class=HTMLResponse)
def package_edit_page(request: Request, package_id: int, db: Session = Depends(get_db)):
    user = require_user(request, db)
    pkg = db.query(Package).filter(Package.package_id == package_id).first()
    if not pkg:
        flash(request, "Package not found", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    agency = db.query(Agency).filter(Agency.registration_id == pkg.registration_id, Agency.user_id == user.id).first()
    if not agency:
        flash(request, "Not allowed to edit this package", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    onward = db.query(PackageFlight).filter_by(package_id=pkg.package_id, leg="onward").first()
    ret = db.query(PackageFlight).filter_by(package_id=pkg.package_id, leg="return").first()
    mecca = db.query(PackageStay).filter_by(package_id=pkg.package_id, city="Mecca").first()
    med = db.query(PackageStay).filter_by(package_id=pkg.package_id, city="Medinah").first()
    incl = db.query(PackageInclusion).filter_by(package_id=pkg.package_id).first()

    flashes = pop_flashes(request)
    return templates.TemplateResponse(
        "package/edit.html",
        {
            "request": request,
            "user": user,
            "flashes": flashes,
            "pkg": pkg,
            "agency": agency,
            "csrf_token": get_csrf_token(request),
            "onward": onward,
            "ret": ret,
            "mecca": mecca,
            "med": med,
            "incl": incl,
        },
    )

@router.post("/package/{package_id}/edit")
def package_edit_submit(
    request: Request,
    package_id: int,
    package_name: str = Form(...),
    days: int = Form(...),
    price: float = Form(...),
    description: str = Form(""),

    # Flights
    onward_date: str = Form(""),
    onward_type: str = Form(""),
    onward_via: str = Form(""),
    onward_airline: str = Form(""),

    return_date: str = Form(""),
    return_type: str = Form(""),
    return_via: str = Form(""),
    return_airline: str = Form(""),

    # Stays
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

    # Inclusions
    incl_meals: str = Form(""),
    incl_laundry: str = Form(""),
    incl_transport: str = Form(""),
    incl_other: str = Form(""),

    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)
    user = require_user(request, db)

    pkg = db.query(Package).filter(Package.package_id == package_id).first()
    if not pkg:
        flash(request, "Package not found", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    agency = db.query(Agency).filter(Agency.registration_id == pkg.registration_id, Agency.user_id == user.id).first()
    if not agency:
        flash(request, "Not allowed to edit this package", "error")
        return RedirectResponse(url="/select-agency", status_code=303)

    # Update base package
    pkg.package_name = package_name.strip()
    pkg.days = days
    pkg.price = price
    pkg.description = _norm(description)

    # --- Flights upsert ---
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

    # --- Stays upsert ---
    def upsert_stay(which_city: str, ci: str, co: str, hotel: str, link: str, dist_m: str, dist_txt: str):
        stay = db.query(PackageStay).filter_by(package_id=pkg.package_id, city=which_city).first()
        if any([ci, co, hotel, link, dist_m, dist_txt]):
            if not stay:
                stay = PackageStay(package_id=pkg.package_id, city=which_city)
                db.add(stay)
            stay.check_in = _to_date(ci)
            stay.check_out = _to_date(co)
            stay.hotel_name = _norm(hotel)
            stay.hotel_link = _norm(link)
            stay.distance_text = _norm(dist_txt)
            stay.distance_m = int(dist_m) if (dist_m or "").strip().isdigit() else None
        elif stay:
            db.delete(stay)

    upsert_stay("Mecca", mecca_check_in, mecca_check_out, mecca_hotel, mecca_link, mecca_distance_m, mecca_distance_text)
    upsert_stay("Medinah", med_check_in, med_check_out, med_hotel, med_link, med_distance_m, med_distance_text)

    # --- Inclusions upsert (1:1) ---
    incl = db.query(PackageInclusion).filter_by(package_id=pkg.package_id).first()
    if any([incl_meals, incl_laundry, incl_transport, incl_other]):
        if not incl:
            incl = PackageInclusion(package_id=pkg.package_id)
            db.add(incl)
        incl.meals = _norm(incl_meals)
        incl.laundry = _norm(incl_laundry)
        incl.transport = _norm(incl_transport)
        incl.other_notes = _norm(incl_other)
    elif incl:
        db.delete(incl)

    db.commit()
    flash(request, "Package updated", "success")
    return RedirectResponse(
        url=f"/agency/{agency.registration_id}/dashboard",
        status_code=303,
    )

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
        Agency.registration_id == pkg.registration_id,
        Agency.user_id == user.id
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

@router.get("/operators", response_class=HTMLResponse)
def operators_list(
    request: Request,
    q: str = Query("", alias="q"),
    country: str | None = Query(None),
    city: str | None = Query(None),
    sort: str = Query("name"),   # name | newest | oldest
    db: Session = Depends(get_db),
):
    query = db.query(Agency)

    # filters
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (Agency.agencies_name.ilike(like)) |
            (Agency.city.ilike(like)) |
            (Agency.country.ilike(like)) |
            (Agency.description.ilike(like))
        )
    if country and country.strip() and country.lower() != "all":
        query = query.filter(Agency.country == country.strip())
    if city and city.strip() and city.lower() != "all":
        query = query.filter(Agency.city == city.strip())

    # sorting
    if sort == "newest":
        query = query.order_by(Agency.registration_id.desc())
    elif sort == "oldest":
        query = query.order_by(Agency.registration_id.asc())
    else:
        query = query.order_by(Agency.agencies_name.asc())

    agencies = query.all()

    countries = [r[0] for r in db.query(Agency.country).distinct().order_by(Agency.country.asc()).all()]
    cities = [r[0] for r in db.query(Agency.city).distinct().order_by(Agency.city.asc()).all()]

    return templates.TemplateResponse(
        "public/operators_list.html",
        {
            "request": request,
            "title": "Operators",
            "agencies": agencies,
            "q": q,
            "country": country or "all",
            "city": city or "all",
            "sort": sort,
            "countries": countries,
            "cities": cities,
        },
    )

@router.get("/operators/{registration_id}", response_class=HTMLResponse)
def operator_detail(registration_id: int, request: Request, db: Session = Depends(get_db)):
    agency = db.query(Agency).filter(Agency.registration_id == registration_id).first()
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")

    packages = db.query(Package).filter(Package.registration_id == registration_id).all()
    detail = db.query(AgencyDetail).filter(AgencyDetail.agency_id == registration_id).first()
    return templates.TemplateResponse(
        "public/operator_detail.html",
        {
            "request": request,
            "title": agency.agencies_name,
            "agency": agency,
            "packages": packages,
            "detail": detail,
        },
    )


# ----------------- Canonical City URLs (public) -----------------

def _decode_city(city_name: str) -> str:
    return urllib.parse.unquote(city_name).strip()

@router.get("/city/{city_name}/operators", response_class=HTMLResponse, name="city_operators")
def city_operators(city_name: str, request: Request, db: Session = Depends(get_db)):
    city = _decode_city(city_name)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    agencies = (
        db.query(Agency)
        .filter(func.lower(Agency.city) == city.lower())
        .order_by(Agency.agencies_name.asc())
        .all()
    )

    return templates.TemplateResponse(
        "public/operators_by_city.html",
        {
            "request": request,
            "title": f"Operators in {city}",
            "city": city,
            "agencies": agencies,
            "count": len(agencies),
        },
    )

@router.get("/city/{city_name}/packages", response_class=HTMLResponse, name="city_packages")
def city_packages(city_name: str, request: Request, db: Session = Depends(get_db)):
    city = _decode_city(city_name)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    agencies = (
        db.query(Agency)
        .filter(func.lower(Agency.city) == city.lower())
        .order_by(Agency.agencies_name.asc())
        .all()
    )
    reg_ids = [a.registration_id for a in agencies]

    packages = []
    agency_by_id = {}
    if reg_ids:
        packages = (
            db.query(Package)
            .filter(Package.registration_id.in_(reg_ids))
            .order_by(Package.package_id.desc())
            .all()
        )
        agency_by_id = {a.registration_id: a for a in agencies}

    return templates.TemplateResponse(
        "public/packages_city.html",
        {
            "request": request,
            "title": f"Packages in {city}",
            "city": city,
            "packages": packages,
            "agency_by_id": agency_by_id,
            "count": len(packages),
        },
    )

@router.get("/city/{city_name}", response_class=HTMLResponse, name="city_hub")
def city_hub(city_name: str, request: Request, db: Session = Depends(get_db)):
    city = _decode_city(city_name)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    agencies = (
        db.query(Agency)
        .filter(func.lower(Agency.city) == city.lower())
        .order_by(Agency.agencies_name.asc())
        .all()
    )

    reg_ids = [a.registration_id for a in agencies]
    packages = []
    agency_by_id = {}
    if reg_ids:
        packages = (
            db.query(Package)
            .filter(Package.registration_id.in_(reg_ids))
            .order_by(Package.package_id.desc())
            .all()
        )
        agency_by_id = {a.registration_id: a for a in agencies}

    return templates.TemplateResponse(
        "public/city_hub.html",
        {
            "request": request,
            "title": f"{city} • Operators & Packages",
            "city": city,
            "agencies": agencies,
            "packages": packages,
            "agency_by_id": agency_by_id,
        },
    )


# ----------------- Legacy redirects -> Canonical -----------------

# Old dashboard path -> new workspace path
@router.get("/dashboard/agency/{registration_id}")
def legacy_dashboard_agency(registration_id: int):
    return RedirectResponse(url=f"/agency/{registration_id}/dashboard", status_code=308)

# Old city package list (singular) -> plural
@router.get("/city/{city_name}/package")
def legacy_city_package(city_name: str):
    return RedirectResponse(url=f"/city/{urllib.parse.quote(city_name)}/packages", status_code=308)

# Old package detail with city -> canonical /packages/{id}
@router.get("/packages/{city}/{package_id}")
def legacy_package_detail(city: str, package_id: int):
    return RedirectResponse(url=f"/packages/{package_id}", status_code=308)

# Older “operators/city/{city}” -> canonical city route
@router.get("/operators/city/{city_name}")
def legacy_operators_city(city_name: str):
    return RedirectResponse(url=f"/city/{urllib.parse.quote(city_name)}/operators", status_code=308)

@router.get("/packages/city/{city_name}")
def legacy_packages_city(city_name: str):
    return RedirectResponse(url=f"/city/{urllib.parse.quote(city_name)}/packages", status_code=308)


PHONE_E164_RE   = re.compile(r"^\+[1-9]\d{7,14}$")       # +<country><nsn> (8–15 digits total)
PHONE_INDIA_RE  = re.compile(r"^[6-9]\d{9}$")            # 10-digit Indian mobile

def normalize_phone(raw: str) -> str:
    """Keep digits and a single leading '+'. Convert leading '00' to '+'. Strip spaces/dashes."""
    s = re.sub(r"[^\d+]", "", (raw or ""))
    if s.startswith("00"):
        s = "+" + s[2:]
    # collapse multiple leading '+' just in case
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
