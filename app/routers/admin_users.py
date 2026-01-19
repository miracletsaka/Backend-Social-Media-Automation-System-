from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session as DbSession
from datetime import timedelta

from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])

@router.get("")
def list_users(db: DbSession = Depends(get_db)):
    rows = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "is_active": u.is_active,
            "is_email_verified": u.is_email_verified,
            "created_at": u.created_at.isoformat(),
        }
        for u in rows
    ]
