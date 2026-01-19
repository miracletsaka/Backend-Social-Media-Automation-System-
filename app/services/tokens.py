import hashlib
import secrets
from datetime import datetime, timedelta, timezone

def new_token() -> str:
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def utcnow():
    return datetime.now(timezone.utc)

def expires_in(minutes: int):
    return utcnow() + timedelta(minutes=minutes)
