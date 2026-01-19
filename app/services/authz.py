from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.models.session import Session
from app.models.user import User
from app.services.sessions import COOKIE_NAME, hash_session_token
from app.services.tokens import utcnow

def get_current_user(req: Request, db: DbSession):
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
    return user

def require_admin(req: Request, db: DbSession = Depends(get_db)):
    user = get_current_user(req, db)
    if getattr(user, "role", "member") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user
