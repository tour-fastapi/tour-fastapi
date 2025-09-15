# scripts/brevo_smoke_test.py
import os, requests, json
from dotenv import load_dotenv

load_dotenv() 
BREVO_URL = "https://api.brevo.com/v3/smtp/email"

API_KEY = os.getenv("BREVO_API_KEY")
FROM_EMAIL = os.getenv("MAIL_FROM_EMAIL", "no-reply@example.com")
FROM_NAME  = os.getenv("MAIL_FROM_NAME", "Tour App")

def send_test(to_email: str):
    payload = {
        "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
        "to": [{"email": to_email}],
        "subject": "Brevo smoke test ✅",
        "htmlContent": "<p>If you can read this, Brevo works 🎉</p>",
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": API_KEY,
    }
    r = requests.post(BREVO_URL, headers=headers, json=payload, timeout=15)
    print("status:", r.status_code)
    try:
        print("body:", json.dumps(r.json(), indent=2))
    except Exception:
        print("text:", r.text)
    r.raise_for_status()

if __name__ == "__main__":
    to = input("Enter a destination email to test (ideally your own): ").strip()
    if not API_KEY:
        raise SystemExit("Set BREVO_API_KEY in your .env (and activate the venv)!")
    send_test(to)
