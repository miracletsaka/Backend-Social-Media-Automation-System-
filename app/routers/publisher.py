from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, asc
from datetime import datetime, timezone

from app.database import get_db
from app.models.content_item import ContentItem

router = APIRouter(prefix="/publisher", tags=["publisher"])

@router.get("/due")
def due(db: Session = Depends(get_db), limit: int = Query(20, ge=1, le=200)):
    now = datetime.now(timezone.utc)

    q = (
        select(ContentItem)
        .where(ContentItem.status == "SCHEDULED")
        .where(ContentItem.scheduled_at.isnot(None))
        .where(ContentItem.scheduled_at <= now)
        .order_by(asc(ContentItem.scheduled_at))
        .limit(limit)
    )

    return db.execute(q).scalars().all()
