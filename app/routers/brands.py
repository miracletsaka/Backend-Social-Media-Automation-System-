from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.brand import Brand
from app.schemas.brand import BrandCreate, BrandUpdate, BrandOut

router = APIRouter(prefix="/brands", tags=["brands"])

@router.get("", response_model=list[BrandOut])
def list_brands(db: Session = Depends(get_db), active_only: bool = True):
    q = select(Brand)
    if active_only:
        q = q.where(Brand.is_active == True)  # noqa
    return db.execute(q).scalars().all()

@router.post("", response_model=BrandOut)
def create_brand(payload: BrandCreate, db: Session = Depends(get_db)):
    existing = db.get(Brand, payload.id)
    if existing:
        raise HTTPException(status_code=400, detail="Brand id already exists")

    brand = Brand(
        id=payload.id.strip(),
        display_name=payload.display_name.strip(),
        is_active=payload.is_active,
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand

@router.patch("/{brand_id}", response_model=BrandOut)
def update_brand(brand_id: str, payload: BrandUpdate, db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    if payload.display_name is not None:
        brand.display_name = payload.display_name.strip()
    if payload.is_active is not None:
        brand.is_active = payload.is_active

    db.commit()
    db.refresh(brand)
    return brand
