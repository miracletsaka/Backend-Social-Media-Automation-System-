# backend/app/routers/media.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem
from app.services.media_generator import generate_media
from app.services.state_machine import ensure_transition

router = APIRouter(prefix="/media", tags=["media"])


def _parse_ids(payload: dict) -> list[uuid.UUID]:
    ids = payload.get("content_item_ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="content_item_ids is required")
    try:
        return [uuid.UUID(x) for x in ids]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid UUID(s)")


@router.post("/generate")
def generate_media_for_items(payload: dict, db: Session = Depends(get_db)):
    """
    Generate media for selected items.
    Allowed: content_type=image|video
    Flow:
      - validate items exist
      - validate status allows generation (APPROVED or REJECTED)
      - generate media_url
      - store on content_item
      - set status -> PENDING_APPROVAL (so user reviews before scheduling/posting)
    """
    uuid_ids = _parse_ids(payload)

    items = db.execute(select(ContentItem).where(ContentItem.id.in_(uuid_ids))).scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    generated = 0
    skipped: list[dict[str, Any]] = []
    now = datetime.utcnow()

    for it in items:
        ct = (it.content_type or "").lower().strip()

        if ct not in ("image", "video"):
            skipped.append({"id": str(it.id), "status": it.status, "reason": f"Not an image/video item: {it.content_type}"})
            continue

        # Only allow generation for APPROVED or REJECTED (your choice)
        if it.status not in ("APPROVED", "REJECTED"):
            skipped.append({"id": str(it.id), "status": it.status, "reason": "Only APPROVED or REJECTED items can generate media"})
            continue

        # Ensure state machine allows -> GENERATING (optional) or direct -> PENDING_APPROVAL
        # If you have GENERATING state, use it.
        try:
            ensure_transition(it.status, "GENERATING")
            it.status = "GENERATING"
        except Exception:
            # If your transitions don't allow, we skip changing to GENERATING
            pass

        prompt = (it.body_text or it.title or "").strip() or "Generate media for this post"

        try:
            out = generate_media(
                brand_id=it.brand_id,
                platform=it.platform,
                content_type=ct,
                prompt=prompt,
            )
        except Exception as e:
            it.status = "FAILED"
            it.last_error = f"media_generator error: {e}"
            it.updated_at = now
            skipped.append({"id": str(it.id), "status": "FAILED", "reason": str(e)})
            continue

        # Store media outputs (these fields must exist in your DB/model)
        setattr(it, "media_url", out.get("media_url"))
        setattr(it, "media_type", out.get("media_type"))
        setattr(it, "thumbnail_url", out.get("thumbnail_url"))
        setattr(it, "media_caption", (getattr(it, "media_caption", None) or it.body_text or it.title))

        # Move to PENDING_APPROVAL after generation
        ensure_transition(it.status, "PENDING_APPROVAL")
        it.status = "PENDING_APPROVAL"

        it.last_error = None
        it.updated_at = now
        generated += 1

    db.commit()
    return {"generated": generated, "skipped": len(skipped), "skipped_items": skipped}
