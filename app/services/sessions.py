import hashlib
import os
import secrets
from datetime import timedelta
from fastapi import Response

from .tokens import utcnow

COOKIE_NAME = "nf_session"

def new_session_token() -> str:
    return secrets.token_urlsafe(32)

def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def set_session_cookie(resp: Response, token: str, minutes: int = 60 * 24 * 7):
    is_prod = os.getenv("ENV") == "production"

    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=is_prod,              # True in prod (HTTPS)
        samesite="lax",
        domain=".neuroflowai.co.uk" if is_prod else None,
        max_age=minutes * 60,
        path="/",
    )

def clear_session_cookie(resp: Response):
    resp.delete_cookie(COOKIE_NAME, path="/")
