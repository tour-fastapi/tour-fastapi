# app/web/routes_admin.py
from __future__ import annotations
import requests
from datetime import datetime
from typing import Union
from app.core.config import settings
from fastapi import APIRouter, Depends, Request, Query, Form,  HTTPException, status 
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.deps import get_db
from app.web.deps import (
    flash,
    get_csrf_token,
    get_current_user_from_cookie,
    pop_flashes,
    require_csrf,
)
from app.web.context import ctx as _ctx, is_admin_user  # ✅ shared helpers

from app.db.models.user import User
from app.db.models.package import Package
from app.db.models.agency import Agency
from app.db.models.inquiry import Inquiry
from app.db.models.agency_branch import AgencyBranch
from app.db.models.hotel import Hotel

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")

#------------------
# Brevo Email send
#------------------
def send_brevo_email(to_email: str, subject: str, html_content: str) -> None:
    """
    Minimal Brevo SMTP email sender using settings.BREVO_API_KEY,
    settings.MAIL_FROM_EMAIL, and settings.MAIL_FROM_NAME.
    """
    if not to_email:
        return

    api_key = settings.BREVO_API_KEY
    if not api_key:
        # Don't break app if not configured
        print("BREVO_API_KEY not configured; email not sent")
        return

    payload = {
        "sender": {
            "email": settings.MAIL_FROM_EMAIL,
            "name": settings.MAIL_FROM_NAME,
        },
        "to": [
            {"email": to_email},
        ],
        "subject": subject,
        "htmlContent": html_content,
    }

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers=headers,
            timeout=10,
        )
        # Optional: inspect resp.status_code / resp.text for logging
        if resp.status_code >= 400:
            print("Brevo email error:", resp.status_code, resp.text)
    except Exception as e:
        print("Error sending Brevo email:", e)


# ---------------------------
# Helpers
# ---------------------------

def _admin_guard(request: Request, db: Session) -> Union[User, RedirectResponse]:
    """
    Return the logged-in admin user on success,
    otherwise a RedirectResponse to /login or /.
    """
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not is_admin_user(user):  # ✅ use shared checker
        return RedirectResponse("/", status_code=303)
    return user


# ---------------------------
# Post-login smart redirect
# ---------------------------
@router.get("/post-login", response_class=HTMLResponse)
def post_login_redirect(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    After successful login, redirect admin to /admin,
    else send to /dashboard (or / if you prefer).
    Use this after login success: RedirectResponse('/post-login', 303)
    """
    user = get_current_user_from_cookie(request, db)
    if user and is_admin_user(user):  # ✅ fixed
        return RedirectResponse(url="/admin", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


# ---------------------------
# Admin: Dashboard
# ---------------------------
@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = _admin_guard(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    stats = {
        "agencies": db.query(Agency).count(),
        "packages": db.query(Package).count(),
        "inquiries": db.query(Inquiry).count(),
        "users": db.query(User).count(),
        "hotels": db.query(Hotel).count(),
    }
    return templates.TemplateResponse(
        "admin/dashboard.html",
        _ctx(request, db, title="Admin • Dashboard", stats=stats),
    )

# ---------------------------
# Admin: Users list
# ---------------------------
from sqlalchemy.orm import selectinload

@router.get("/admin/users", response_class=HTMLResponse)
def admin_users(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    # ✅ Admin guard
    user_or_redirect = _admin_guard(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    # ✅ Query all users (you can add .options(...) if relationships exist)
    q = (
        db.query(User)
        .order_by(User.id.desc())
    )

    total = q.count()
    items = q.limit(limit).offset((page - 1) * limit).all()

    # ✅ Render the user list template
    return templates.TemplateResponse(
        "admin/users_list.html",  # make sure the filename matches your template
        _ctx(
            request,
            db,
            title="Admin — Users",
            items=items,
            page=page,
            limit=limit,
            total=total,
        ),
    )


# ---------------------------
# Admin: Packages list
# ---------------------------
@router.get("/admin/packages", response_class=HTMLResponse)
def admin_packages(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    user_or_redirect = _admin_guard(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    q = db.query(Package).order_by(Package.package_id.desc())
    items = q.limit(limit).offset((page - 1) * limit).all()

    return templates.TemplateResponse(
        "admin/packages_list.html",
        _ctx(
            request,
            db,
            title="Admin — Packages",
            items=items,
            page=page,
            limit=limit,
        ),
    )


# ---------------------------
# Admin: Agencies list
# ---------------------------
from sqlalchemy.orm import selectinload



from sqlalchemy.orm import selectinload
from sqlalchemy import func, case

@router.get("/admin/agencies", response_class=HTMLResponse)
def admin_agencies(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    user_or_redirect = _admin_guard(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    # 1 = unread (viewed_by_admin == False), 0 = read
    unread_order = case(
        (Agency.viewed_by_admin == False, 1),
        else_=0,
    )

    # last change timestamp
    last_change = func.coalesce(Agency.updated_at, Agency.created_at)

    q = (
        db.query(Agency)
        .options(
            selectinload(Agency.city_rel),
            selectinload(Agency.user),
        )
        .order_by(
            unread_order.desc(),   # 🥇 unread first
            last_change.desc(),    # 🥈 latest updated/created first
        )
    )

    total = q.count()
    items = q.limit(limit).offset((page - 1) * limit).all()

    response = templates.TemplateResponse(
        "admin/agencies_list.html",
        _ctx(
            request,
            db,
            title="Agencies",
            items=items,
            page=page,
            limit=limit,
            total=total,
        ),
    )
    response.headers["Cache-Control"] = "no-store"
    return response






# ---------------------------
# Admin: Agency detail
# ---------------------------
@router.get("/admin/agencies/{registration_id}", response_class=HTMLResponse)
def admin_agency_detail(
    registration_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_or_redirect = _admin_guard(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    # Agency
    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == registration_id)
        .first()
    )
    if not agency:
        flash(request, "Agency not found.", "error")
        return RedirectResponse(url="/admin/agencies", status_code=303)

    # ✅ Mark as viewed and commit if needed
    if not getattr(agency, "viewed_by_admin", False):
        agency.viewed_by_admin = True
        db.flush()   # not strictly required, but safe
        db.commit() 

    # Owner
    owner = db.query(User).filter(User.id == agency.user_id).first()

    # Branches
    branches = (
        db.query(AgencyBranch)
        .filter(AgencyBranch.agency_id == agency.registration_id)
        .order_by(AgencyBranch.is_main.desc(), AgencyBranch.name.asc())
        .all()
    )

    # Packages
    pkgs = (
        db.query(Package)
        .filter(Package.registration_id == agency.registration_id)
        .order_by(Package.package_id.desc())
        .all()
    )

    # Recent inquiries (limit 20)
    inquiries = (
        db.query(Inquiry)
        .filter(Inquiry.registration_id == agency.registration_id)
        .order_by(Inquiry.inquiry_id.desc())
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        "admin/agency_detail.html",
        _ctx(
            request,
            db,
            title=f"Agency • {agency.agencies_name}",
            agency=agency,
            owner=owner,
            branches=branches,
            packages=pkgs,
            inquiries=inquiries,
        ),
    )

@router.post("/admin/agencies/{registration_id}/edit")
async def admin_agency_update(
    registration_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_or_redirect = _admin_guard(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    agency = (
        db.query(Agency)
        .filter(Agency.registration_id == registration_id)
        .first()
    )
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")

    form = await request.form()

    # 🔁 update fields from your form
    agency.agencies_name = form.get("agencies_name") or agency.agencies_name
    agency.city = form.get("city") or agency.city
    mark_agency_updated_for_admin(agency)
    db.commit()
    db.refresh(agency)

    # 🔴 IMPORTANT CHANGE: go back to list, not detail
    return RedirectResponse(
        url="/admin/agencies",
        status_code=status.HTTP_303_SEE_OTHER,
    )

# helpers for agency updates
from datetime import datetime, timezone

def mark_agency_updated_for_admin(agency):
    """
    Whenever an agency is changed (by operator or admin),
    call this so it appears as UNREAD + UPDATED for admin.
    """
    agency.updated_at = datetime.now(timezone.utc)
    agency.viewed_by_admin = False


# ---------------------------
# Admin: Inquiries list
# ---------------------------
@router.get("/admin/inquiries", response_class=HTMLResponse)
def admin_inquiries(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    user_or_redirect = _admin_guard(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    q = db.query(Inquiry).order_by(Inquiry.inquiry_id.desc())
    items = q.limit(limit).offset((page - 1) * limit).all()

    return templates.TemplateResponse(
        "admin/inquiries_list.html",
        _ctx(
            request,
            db,
            title="Admin — Inquiries",
            items=items,
            page=page,
            limit=limit,
        ),
    )


# ---------------------------
# Admin: Void / Unvoid Agency
# ---------------------------
@router.post("/admin/agencies/{registration_id}/void")
def admin_void_agency(
    registration_id: int,
    request: Request,
    reason: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)

    user_or_redirect = _admin_guard(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    admin_user: User = user_or_redirect
    reason = (reason or "").strip()

    # 🔥 Validate mandatory reason
    if not reason:
        flash(request, "Reason is required to block an agency.", "error")
        return RedirectResponse(
            url=f"/admin/agencies/{registration_id}", status_code=303
        )
    
    agency = db.query(Agency).filter(Agency.registration_id == registration_id).first()
    if not agency:
        flash(request, "Agency not found.", "error")
        return RedirectResponse(url="/admin/agencies", status_code=303)

    # --- mark blocked in DB ---
    agency.is_blocked = True
    agency.blocked_at = datetime.utcnow()
    agency.blocked_reason = reason
    agency.blocked_by_user_id = getattr(admin_user, "id", None)
    db.commit()

    # --- send Brevo email to agency owner ---
    owner = db.query(User).filter(User.id == agency.user_id).first()
    to_email = owner.email if owner and owner.email else None
    block_reason = agency.blocked_reason or "No reason specified."

    if to_email:
        subject = "Your Umrah Advisor account has been blocked"
        html_content = f"""
        <p>Assalamu Alaikum,</p>
        <p>Your agency account <strong>{agency.agencies_name}</strong> on Umrah Advisor has been <strong>blocked by the admin</strong>.</p>
        <p><strong>Reason:</strong> {block_reason}</p>
        <p>If you believe this is a mistake or need clarification, please contact our support team:</p>
        <p><a href="mailto:umrahadvisor1@gmail.com">umrahadvisor1@gmail.com</a></p>
        <p>JazakAllahu Khair,<br>{settings.MAIL_FROM_NAME}</p>
        """

        send_brevo_email(to_email, subject, html_content)

    flash(request, f"Agency '{agency.agencies_name}' has been blocked.", "success")
    return RedirectResponse(url=f"/admin/agencies/{registration_id}", status_code=303)



@router.post("/admin/agencies/{registration_id}/unvoid")
def admin_unvoid_agency(
    registration_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    require_csrf(request, csrf_token)

    user_or_redirect = _admin_guard(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    agency = db.query(Agency).filter(Agency.registration_id == registration_id).first()
    if not agency:
        flash(request, "Agency not found.", "error")
        return RedirectResponse(url="/admin/agencies", status_code=303)

    # --- mark unblocked in DB ---
    agency.is_blocked = False
    agency.blocked_at = None
    agency.blocked_reason = None
    agency.blocked_by_user_id = None
    db.commit()

    # --- send Brevo email to agency owner ---
    owner = db.query(User).filter(User.id == agency.user_id).first()
    to_email = owner.email if owner and owner.email else None

    if to_email:
        subject = "Your Umrah Advisor account has been restored"
        html_content = f"""
        <p>Assalamu Alaikum,</p>
        <p>Your agency account <strong>{agency.agencies_name}</strong> on Umrah Advisor has been <strong>restored</strong> and is now active again.</p>
        <p>You can log in and continue using your account as usual.</p>
        <p>If you have any questions, please contact our support team:</p>
        <p><a href="mailto:umrahadvisor1@gmail.com">umrahadvisor1@gmail.com</a></p>
        <p>JazakAllahu Khair,<br>{settings.MAIL_FROM_NAME}</p>
        """

        send_brevo_email(to_email, subject, html_content)

    flash(request, f"Agency '{agency.agencies_name}' has been unblocked.", "success")
    return RedirectResponse(url=f"/admin/agencies/{registration_id}", status_code=303)

@router.get("/admin/hotels", response_class=HTMLResponse)
def admin_hotels_choice(request: Request, db: Session = Depends(get_db)):
    # ✅ Use the same guard you use everywhere else
    user_or_redirect = _admin_guard(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    return templates.TemplateResponse(
        "admin/hotels_choice.html",
        _ctx(request, db, title="Admin — Hotels"),
    )

@router.get("/admin/hotels/{city}", response_class=HTMLResponse)
def admin_hotels_list(
    city: str,
    request: Request,
    db: Session = Depends(get_db),
):
    user_or_redirect = _admin_guard(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    # Normalize city
    city_norm = city.capitalize()
    if city_norm not in ("Mecca", "Medinah"):
        raise HTTPException(status_code=404, detail="Invalid city")

    hotels = (
        db.query(Hotel)
        .filter(Hotel.city == city_norm)
        .order_by(Hotel.name.asc())
        .all()
    )

    return templates.TemplateResponse(
        "admin/hotels_list.html",
        _ctx(
            request,
            db,
            title=f"Admin — {city_norm} Hotels",
            city=city_norm,
            hotels=hotels,
        ),
    )
