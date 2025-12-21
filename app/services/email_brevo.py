# app/services/email_brevo.py
import requests
from app.core.config import settings

BREVO_API = "https://api.brevo.com/v3/smtp/email"

def send_email_brevo(to_email: str, subject: str, html_content: str):
    key = settings.BREVO_API_KEY
    print("BREVO KEY LOADED:", bool(settings.BREVO_API_KEY), "LEN:", len(settings.BREVO_API_KEY or ""))
    if not key:
        raise RuntimeError("BREVO_API_KEY missing")

    payload = {
        "sender": {"email": settings.MAIL_FROM_EMAIL, "name": settings.MAIL_FROM_NAME},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }

    r = requests.post(
        BREVO_API,
        json=payload,
        headers={
            "api-key": key,
            "accept": "application/json",
            "content-type": "application/json",
        },
        timeout=20,
    )

    if r.status_code >= 400:
        key_tail = key[-4:] if isinstance(key, str) else "????"
        raise RuntimeError(f"Brevo error {r.status_code} key_endswith={key_tail} body={r.text}")

    return r.json()
