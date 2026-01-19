from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from datetime import timedelta

from app.database import get_db
from app.models.user import User
from app.models.session import Session as Session
from app.models.email_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from sqlalchemy.orm import Session as DbSession
from app.services.passwords import hash_password, verify_password, generate_temp_password
from app.services.tokens import new_token, hash_token, utcnow, expires_in
from app.services.mailer import send_email, verify_link, reset_link
from app.services.sessions import new_session_token, hash_session_token, set_session_cookie, clear_session_cookie, COOKIE_NAME

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterIn(BaseModel):
    email: EmailStr

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ResetRequestIn(BaseModel):
    email: EmailStr

class ResetConfirmIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


@router.post("/register")
async def register(payload: RegisterIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    exists = db.query(User).filter(User.email == email).first()
    if exists:
        # Don't leak; but for internal you can still show message
        raise HTTPException(status_code=400, detail="Email already registered")
    
    temp_password = generate_temp_password(12)

    user = User(email=email, password_hash=hash_password(temp_password), is_email_verified=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = new_token()
    t = EmailVerificationToken(
        user_id=user.id,
        token=hash_token(token),
        expires_at=expires_in(24*60),
        used_at=None,
    )
    db.add(t)
    db.commit()

    link = verify_link(token)
    await send_email(
        to=user.email,
        subject="Verify your email",
        # best email template with css styles inline
        html=f"<p>Welcome! Please verify your email by clicking the link below:</p><p><a href='{link}'>{link}</a></p><p>Your temporary password is: <strong>{temp_password}</strong></p><p>Please change your password in settings after logging in.</p>",
    )

    return {"ok": True, "message": "Check your email to verify your account."}

from datetime import datetime, timezone
from fastapi import Depends, HTTPException

@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    def utcnow_aware() -> datetime:
        return datetime.now(timezone.utc)

    th = hash_token(token)

    row = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.token == th)
        .first()
    )

    if not row or row.used_at is not None:
        raise HTTPException(status_code=400, detail="Invalid or used token")

    # --- FIX: make expires_at timezone-aware (assume UTC if naive) ---
    expires_at = row.expires_at
    if expires_at is None:
        raise HTTPException(status_code=400, detail="Token expired")

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < utcnow_aware():
        raise HTTPException(status_code=400, detail="Token expired")
    # ---------------------------------------------------------------

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.is_email_verified = True

    # used_at: store consistent UTC-aware timestamp
    row.used_at = utcnow_aware()

    db.commit()

    return {"ok": True}


@router.post("/login")
def login(payload: LoginIn, req: Request, resp: Response, db: DbSession = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_email_verified:
        raise HTTPException(status_code=403, detail="Email not verified")

    st = new_session_token()
    sess = Session(
        user_id=user.id,
        session_token=hash_session_token(st),
        expires_at=utcnow() + timedelta(days=7),
        revoked_at=None,
        user_agent=req.headers.get("user-agent"),
        ip_address=req.client.host if req.client else None,
    )
    db.add(sess)
    db.commit()

    set_session_cookie(resp, st)
    print("SET COOKIE HEADER:", resp.headers.get("set-cookie"))
    return {"ok": True}

@router.post("/logout")
def logout(req: Request, resp: Response, db: Session = Depends(get_db)):
    raw = req.cookies.get(COOKIE_NAME)
    if raw:
        sh = hash_session_token(raw)
        sess = db.query(Session).filter(Session.session_token == sh, Session.revoked_at == None).first()
        if sess:
            sess.revoked_at = utcnow()
            db.commit()
    clear_session_cookie(resp)
    return {"ok": True}

@router.get("/me")
def me(req: Request, db: DbSession = Depends(get_db)):
    raw = req.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sh = hash_session_token(raw)

    sess = (
        db.query(Session)
        .filter(Session.session_token == sh, Session.revoked_at.is_(None))
        .first()
    )
    if not sess or sess.expires_at < utcnow():
        raise HTTPException(status_code=401, detail="Session expired")

    user = db.query(User).filter(User.id == sess.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {"id": str(user.id), "email": user.email, "is_email_verified": user.is_email_verified}

@router.post("/password-reset/request")
async def password_reset_request(payload: ResetRequestIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    # Always return ok (anti-enumeration)
    if not user:
        return {"ok": True}

    token = new_token()
    row = PasswordResetToken(
        user_id=user.id,
        token=hash_token(token),
        expires_at=expires_in(45),
        used_at=None,
    )
    db.add(row)
    db.commit()

    link = reset_link(token)
    await send_email(
        to=user.email,
        subject="Reset your password",
        html=f"<p>Reset your password:</p><p><a href='{link}'>{link}</a></p>",
    )
    return {"ok": True}

@router.post("/password-reset/confirm")
def password_reset_confirm(payload: ResetConfirmIn, db: Session = Depends(get_db)):
    th = hash_token(payload.token)
    row = db.query(PasswordResetToken).filter(PasswordResetToken.token == th).first()
    if not row or row.used_at is not None:
        raise HTTPException(status_code=400, detail="Invalid or used token")
    if row.expires_at < utcnow():
        raise HTTPException(status_code=400, detail="Token expired")

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.password_hash = hash_password(payload.new_password)
    row.used_at = utcnow()

    # Optional: revoke sessions for safety
    db.query(Session).filter(Session.user_id == user.id, Session.revoked_at == None).update(
        {"revoked_at": utcnow()}
    )

    db.commit()
    return {"ok": True}

@router.post("/change-password")
def change_password(payload: ChangePasswordIn, req: Request, db: Session = Depends(get_db)):
    raw = req.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sh = hash_session_token(raw)
    sess = db.query(Session).filter(Session.session_token == sh, Session.revoked_at == None).first()
    if not sess or sess.expires_at < utcnow():
        raise HTTPException(status_code=401, detail="Session expired")

    user = db.query(User).filter(User.id == sess.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    # verify current password
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # prevent same password reuse (optional but good)
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="New password must be different")

    user.password_hash = hash_password(payload.new_password)

    # revoke other sessions (keep this one)
    db.query(Session).filter(
        Session.user_id == user.id,
        Session.revoked_at == None,
        Session.session_token != sh,
    ).update({"revoked_at": utcnow()})

    db.commit()
    return {"ok": True}

