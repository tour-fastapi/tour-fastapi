# app/web/deps.py
import secrets
import hmac
from typing import Optional

from fastapi import HTTPException, Request, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.security import decode_token
from app.db.models.user import User

# Cookie that stores your access token (set in routes with set_access_cookie)
COOKIE_NAME = "access_token"

# ---- Flash messages (for Jinja templates) ----
def flash(request: Request, text: str, type_: str = "info") -> None:
    request.session.setdefault("flashes", []).append({"text": text, "type": type_})

def pop_flashes(request: Request):
    return request.session.pop("flashes", [])

# ---- CSRF helpers ----
# We keep a single per-session token and compare it on POST.
# Name must match what templates post as <input name="csrf_token" ...>
_CSRF_SESSION_KEY = "csrf_token"

def get_csrf_token(request: Request) -> str:
    """
    Return the existing CSRF token from session, or create one and store it.
    Render this value into forms as a hidden field named 'csrf_token'.
    """
    token = request.session.get(_CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[_CSRF_SESSION_KEY] = token
    return token

def require_csrf(request: Request, token_from_form: Optional[str]) -> None:
    """
    Compare the posted token with the one stored in the session.
    Raise 400 if missing or mismatch.
    """
    if not token_from_form:
        raise HTTPException(status_code=400, detail="Missing CSRF token")

    expected = request.session.get(_CSRF_SESSION_KEY)
    if not expected:
        raise HTTPException(status_code=400, detail="CSRF token not in session")

    # constant-time compare to avoid timing attacks
    if not hmac.compare_digest(expected, token_from_form):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")

# ---- Auth helpers (cookie-based) ----
def get_current_user_from_cookie(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Read 'access_token' cookie, decode JWT, and fetch the User.
    Returns None if missing/invalid.
    """
    raw = request.cookies.get(COOKIE_NAME)
    if not raw or not raw.startswith("Bearer "):
        return None

    token = raw.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    return db.get(User, int(user_id))

def require_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    Same as get_current_user_from_cookie, but raises 401 if unauthenticated.
    Use this as a dependency inside protected routes.
    """
    user = get_current_user_from_cookie(request, db)
    if not user:
        # Do redirects in the route; here we signal auth failure.
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
