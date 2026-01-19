from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.platform import Platform
from app.schemas.platform import PlatformCreate, PlatformUpdate, PlatformOut

router = APIRouter(prefix="/platforms", tags=["platforms"])

@router.get("", response_model=list[PlatformOut])
def list_platforms(db: Session = Depends(get_db), active_only: bool = True):
    q = select(Platform)
    if active_only:
        q = q.where(Platform.is_active == True)  # noqa
    return db.execute(q).scalars().all()

@router.post("", response_model=PlatformOut)
def create_platform(payload: PlatformCreate, db: Session = Depends(get_db)):
    existing = db.get(Platform, payload.id)
    if existing:
        raise HTTPException(status_code=400, detail="Platform id already exists")

    p = Platform(
        id=payload.id.strip().lower(),
        display_name=payload.display_name.strip(),
        is_active=payload.is_active,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@router.patch("/{platform_id}", response_model=PlatformOut)
def update_platform(platform_id: str, payload: PlatformUpdate, db: Session = Depends(get_db)):
    p = db.get(Platform, platform_id)
    if not p:
        raise HTTPException(status_code=404, detail="Platform not found")

    if payload.display_name is not None:
        p.display_name = payload.display_name.strip()
    if payload.is_active is not None:
        p.is_active = payload.is_active

    db.commit()
    db.refresh(p)
    return p
