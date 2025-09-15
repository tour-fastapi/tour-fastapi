# app/services/email_brevo.py
import os, requests
from app.core.config import settings

BREVO_API = "https://api.brevo.com/v3/smtp/email"

def send_email_brevo(to_email: str, subject: str, html_content: str):
    key = settings.BREVO_API_KEY
    if not key:
        raise RuntimeError("BREVO_API_KEY missing")
    payload = {
        "sender": {"email": settings.MAIL_FROM_EMAIL, "name": settings.MAIL_FROM_NAME},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    r = requests.post(BREVO_API, json=payload, headers={"api-key": key, "accept": "application/json", "content-type": "application/json"})
    r.raise_for_status()
    return r.json()
