from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
import uuid

from app.database import get_db
from app.models.content_item import ContentItem
from app.services.state_machine import ensure_transition

router = APIRouter(prefix="/publishing", tags=["publishing"])


def _parse_ids(payload: dict) -> list[uuid.UUID]:
    ids = payload.get("content_item_ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="content_item_ids is required")
    try:
        return [uuid.UUID(x) for x in ids]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid UUID(s)")


@router.post("/mark-published")
def mark_published(payload: dict, db: Session = Depends(get_db)):
    uuid_ids = _parse_ids(payload)
    published_url = (payload.get("published_url") or "").strip() or None

    items = db.execute(select(ContentItem).where(ContentItem.id.in_(uuid_ids))).scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    moved = 0
    skipped = []

    for it in items:
        # strict: only QUEUED -> PUBLISHED
        if it.status != "QUEUED":
            skipped.append({"id": str(it.id), "status": it.status, "reason": "Only QUEUED items can be published"})
            continue

        ensure_transition(it.status, "PUBLISHED")
        it.status = "PUBLISHED"
        it.published_at = datetime.utcnow()
        if published_url:
            it.published_url = published_url
        moved += 1

    db.commit()
    return {"published": moved, "skipped": len(skipped), "skipped_items": skipped}


@router.post("/undo-queued")
def undo_queued(payload: dict, db: Session = Depends(get_db)):
    uuid_ids = _parse_ids(payload)

    items = db.execute(select(ContentItem).where(ContentItem.id.in_(uuid_ids))).scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    moved = 0
    skipped = []

    for it in items:
        if it.status != "QUEUED":
            skipped.append({"id": str(it.id), "status": it.status, "reason": "Only QUEUED items can be reverted"})
            continue

        ensure_transition(it.status, "SCHEDULED")
        it.status = "SCHEDULED"
        moved += 1

    db.commit()
    return {"reverted": moved, "skipped": len(skipped), "skipped_items": skipped}


@router.post("/retry-failed")
def retry_failed(payload: dict, db: Session = Depends(get_db)):
    uuid_ids = _parse_ids(payload)

    items = db.execute(select(ContentItem).where(ContentItem.id.in_(uuid_ids))).scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    moved = 0
    skipped = []

    for it in items:
        if it.status != "FAILED":
            skipped.append({"id": str(it.id), "status": it.status, "reason": "Only FAILED items can be retried"})
            continue

        # you can choose where retries go; I recommend SCHEDULED if it was previously scheduled
        ensure_transition(it.status, "SCHEDULED")
        it.status = "SCHEDULED"
        it.last_error = None
        # attempt_count exists in your DB now — ensure model has it too
        it.attempt_count = (it.attempt_count or 0) + 1
        moved += 1

    db.commit()
    return {"retried": moved, "skipped": len(skipped), "skipped_items": skipped}
