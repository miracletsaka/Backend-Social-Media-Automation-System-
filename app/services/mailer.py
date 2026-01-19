import os
import httpx

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM = os.getenv("RESEND_FROM", "NeuroFlow <no-reply@yourdomain.com>").strip()
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000").strip()

async def send_email(to: str, subject: str, html: str):

    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not set")

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            "https://api.resend.com/emails",
            headers = {
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"from": RESEND_FROM, "to": [to], "subject": subject, "html": html},
        )
        r.raise_for_status()
        return r.json()

def verify_link(token: str) -> str:
    return f"{APP_BASE_URL}/auth/verify?token={token}"

def reset_link(token: str) -> str:
    return f"{APP_BASE_URL}/reset-password?token={token}"
