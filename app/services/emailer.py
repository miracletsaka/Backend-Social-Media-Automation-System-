from __future__ import annotations
import os
import resend

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
MAIL_FROM = os.getenv("MAIL_FROM", "").strip()

def _require():
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not set")
    if not MAIL_FROM:
        raise RuntimeError("MAIL_FROM is not set")

def send_verify_email(to_email: str, verify_url: str):
    _require()
    resend.api_key = RESEND_API_KEY

    subject = "Verify your NeuroFlow account"
    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.5">
      <h2>Verify your email</h2>
      <p>Click the button below to verify your email address.</p>
      <p><a href="{verify_url}" style="background:#111;color:#fff;padding:12px 16px;border-radius:10px;text-decoration:none">Verify Email</a></p>
      <p style="color:#666;font-size:12px">If you didn’t create this account, ignore this email.</p>
    </div>
    """

    resend.Emails.send({
        "from": MAIL_FROM,
        "to": [to_email],
        "subject": subject,
        "html": html,
    })
