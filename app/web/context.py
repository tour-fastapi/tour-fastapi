# app/web/context.py
from __future__ import annotations

from typing import Optional
from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.web.deps import (
    get_current_user_from_cookie,
    pop_flashes,
    get_csrf_token,
)
from app.db.models.user import User

DEFAULT_ADMIN_EMAILS = {"umrahadvisor@gmail.com", "umrahadvisor1@gmail.com"}


def _normalize_admin_emails() -> set[str]:
    configured = getattr(settings, "ADMIN_EMAILS", None)
    emails = configured if configured else DEFAULT_ADMIN_EMAILS
    return {(e or "").strip().lower() for e in emails}


def is_admin_user(user: Optional[User]) -> bool:
    if not user or not getattr(user, "email", None):
        return False
    return (user.email or "").strip().lower() in _normalize_admin_emails() or bool(getattr(user, "is_admin", False))


def ctx(request: Request, db: Session, **extra):
    """
    Shared template context: request, flashes, csrf_token, user, is_admin.
    Import and use this across all route modules to avoid circular imports.
    """
    user = get_current_user_from_cookie(request, db)
    context = {
        "request": request,
        "flashes": pop_flashes(request),
        "csrf_token": get_csrf_token(request),
        "user": user,
        "is_admin": is_admin_user(user),
    }
    context.update(extra or {})
    return context
