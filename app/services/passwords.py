from passlib.context import CryptContext
import secrets
import string

pwd = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)

def hash_password(password: str) -> str:
    return pwd.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd.verify(password, password_hash)

import secrets
import string

def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
