from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
import uuid

from app.database import get_db
from app.models.content_item import ContentItem
from app.services.state_machine import ensure_transition

router = APIRouter(prefix="/schedule", tags=["schedule"])

@router.post("/bulk")
def bulk_schedule(payload: dict, db: Session = Depends(get_db)):
    ids = payload.get("content_item_ids", [])
    scheduled_at = payload.get("scheduled_at")

    if not ids:
        raise HTTPException(status_code=400, detail="content_item_ids is required")
    if not scheduled_at:
        raise HTTPException(status_code=400, detail="scheduled_at is required")

    # Parse datetime (supports 'Z')
    try:
        dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="scheduled_at must be ISO datetime string")

    # UUID validate
    try:
        uuid_ids = [uuid.UUID(x) for x in ids]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid UUID(s) in content_item_ids")

    items = db.execute(select(ContentItem).where(ContentItem.id.in_(uuid_ids))).scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    # enforce status transition + only APPROVED
    for it in items:
        ensure_transition(it.status, "SCHEDULED")  # will raise if invalid
        if it.status != "APPROVED":
            raise HTTPException(status_code=400, detail=f"Item {it.id} must be APPROVED to schedule")

    for it in items:
        it.scheduled_at = dt
        it.status = "SCHEDULED"
        it.last_error = None  # clear previous publish error
        # do not change attempt_count here

    db.commit()
    return {"scheduled": len(items), "scheduled_at": dt.isoformat()}