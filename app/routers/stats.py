from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    by_status = db.execute(text("""
        SELECT status, COUNT(*)::int AS count
        FROM content_items
        GROUP BY status
        ORDER BY status;
    """)).mappings().all()

    by_platform = db.execute(text("""
        SELECT platform, COUNT(*)::int AS count
        FROM content_items
        GROUP BY platform
        ORDER BY platform;
    """)).mappings().all()

    by_brand = db.execute(text("""
        SELECT brand_id, COUNT(*)::int AS count
        FROM content_items
        GROUP BY brand_id
        ORDER BY brand_id;
    """)).mappings().all()

    return {
        "by_status": by_status,
        "by_platform": by_platform,
        "by_brand": by_brand,
    }

