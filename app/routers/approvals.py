from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem
from app.services.state_machine import ensure_transition

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _parse_ids(payload: dict) -> list[str]:
    ids = payload.get("content_item_ids", [])
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="content_item_ids must be a non-empty list")
    return [str(x) for x in ids]


@router.post("/approve")
def approve(payload: dict, db: Session = Depends(get_db)):
    ids = _parse_ids(payload)

    items = db.execute(select(ContentItem).where(ContentItem.id.in_(ids))).scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    approved = 0
    skipped: list[dict[str, Any]] = []
    now = datetime.utcnow()

    for item in items:
        # ✅ Only approve drafts that are actually ready for review
        if item.status not in ("PENDING_APPROVAL", "DRAFT_READY"):
            skipped.append(
                {"id": str(item.id), "status": item.status, "reason": "Item must be PENDING_APPROVAL/DRAFT_READY first"}
            )
            continue

        try:
            ensure_transition(item.status, "APPROVED")
            item.status = "APPROVED"
        except Exception as e:
            skipped.append({"id": str(item.id), "status": item.status, "reason": str(e)})
            continue

        item.updated_at = now
        item.last_error = None
        approved += 1

    db.commit()
    return {"approved": approved, "skipped": len(skipped), "skipped_items": skipped}


@router.post("/reject")
def reject(payload: dict, db: Session = Depends(get_db)):
    ids = _parse_ids(payload)
    reason = (payload.get("reason") or "").strip() or None

    items = db.execute(select(ContentItem).where(ContentItem.id.in_(ids))).scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    rejected = 0
    skipped: list[dict[str, Any]] = []
    now = datetime.utcnow()

    for item in items:
        # ✅ Same rule: only reject items that were reviewed
        if item.status not in ("PENDING_APPROVAL", "DRAFT_READY"):
            skipped.append(
                {"id": str(item.id), "status": item.status, "reason": "Item must be PENDING_APPROVAL/DRAFT_READY first"}
            )
            continue

        try:
            ensure_transition(item.status, "REJECTED")
            item.status = "REJECTED"
        except Exception as e:
            skipped.append({"id": str(item.id), "status": item.status, "reason": str(e)})
            continue

        item.updated_at = now
        item.last_error = reason
        rejected += 1

    db.commit()
    return {"rejected": rejected, "skipped": len(skipped), "skipped_items": skipped}
