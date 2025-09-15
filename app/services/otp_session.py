# app/services/otp_session.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import secrets
from fastapi import Request

# ---------- tiny helpers ----------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def generate_numeric_otp(n: int = 6) -> str:
    """
    Generate a zero-padded numeric OTP with n digits (default 6).
    """
    if n < 1:
        n = 6
    # Use secrets for cryptographic randomness
    upper = 10 ** n
    num = secrets.randbelow(upper)
    return f"{num:0{n}d}"

# ---------- public API we use from routes ----------

def new_otp_ctx(
    request: Request,
    *,
    email: str,
    user_id: int | None,
    purpose: str = "login",
    minutes: int = 5,
    code_len: int = 6,
    max_attempts: int = 6,
) -> dict:
    """
    Create a fresh OTP context in the session. Overwrites any previous one.
    """
    code = generate_numeric_otp(code_len)
    ctx = {
        "code": code,
        "email": email,
        "user_id": user_id,
        "purpose": purpose,
        "created_at": _utcnow().isoformat(),
        "expires_at": (_utcnow() + timedelta(minutes=minutes)).isoformat(),
        "attempts_left": max_attempts,
    }
    request.session["otp_ctx"] = ctx
    # You may also want to keep user_id separately for post-verify login issuance
    request.session["post_otp_user_id"] = user_id
    return ctx

def get_otp_ctx(request: Request) -> dict | None:
    """
    Read current OTP context from the session, or None.
    """
    ctx = request.session.get("otp_ctx")
    if not isinstance(ctx, dict):
        return None
    return ctx

def clear_otp_ctx(request: Request) -> None:
    """
    Remove the OTP context from the session.
    """
    request.session.pop("otp_ctx", None)

def _is_expired(ctx: dict) -> bool:
    """
    Check if the OTP is expired based on stored expires_at.
    """
    expires_at = ctx.get("expires_at")
    if not expires_at:
        return True
    try:
        exp = datetime.fromisoformat(expires_at)
    except Exception:
        return True
    return _utcnow() > exp

def check_code_and_update(request: Request, code: str) -> tuple[bool, str]:
    """
    Compare submitted code with session’s OTP. Decrement attempts.
    Return (ok, message). On success, clears OTP context.
    """
    ctx = get_otp_ctx(request)
    if not ctx:
        return False, "No OTP session found. Please log in again."

    if _is_expired(ctx):
        clear_otp_ctx(request)
        return False, "OTP expired. Please log in again."

    attempts_left = int(ctx.get("attempts_left", 0))
    if attempts_left <= 0:
        clear_otp_ctx(request)
        return False, "Too many attempts. Please log in again."

    # Normalize inputs
    submitted = (code or "").strip()
    real = str(ctx.get("code", "")).strip()

    # Wrong code -> decrement attempts and keep ctx
    if not submitted or submitted != real:
        attempts_left -= 1
        ctx["attempts_left"] = attempts_left
        request.session["otp_ctx"] = ctx  # persist updated attempts
        if attempts_left <= 0:
            clear_otp_ctx(request)
            return False, "Too many incorrect attempts. Please log in again."
        return False, f"Invalid code. {attempts_left} attempt(s) remaining."

    # Correct -> success, clear otp
    clear_otp_ctx(request)
    return True, "OTP verified."
