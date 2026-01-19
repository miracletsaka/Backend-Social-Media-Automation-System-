from __future__ import annotations
import secrets
from datetime import datetime, timedelta
from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd.verify(password, password_hash)

def new_token(nbytes: int = 32) -> str:
    # urlsafe token ~ 43 chars for 32 bytes
    return secrets.token_urlsafe(nbytes)

def utcnow() -> datetime:
    return datetime.utcnow()

def expires_in_days(days: int) -> datetime:
    return utcnow() + timedelta(days=days)

def expires_in_minutes(minutes: int) -> datetime:
    return utcnow() + timedelta(minutes=minutes)
