from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem
from app.services.state_machine import ensure_transition

router = APIRouter(prefix="/generation", tags=["generation"])


def _parse_ids(payload: dict) -> list[uuid.UUID]:
    ids = payload.get("content_item_ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="content_item_ids is required")
    try:
        return [uuid.UUID(x) for x in ids]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid UUID(s)")


def _require_make_config():
    url = os.getenv("MAKE_MEDIA_WEBHOOK_URL", "").strip()
    key = os.getenv("MAKE_API_KEY", "").strip()
    if not url:
        raise HTTPException(status_code=500, detail="MAKE_MEDIA_WEBHOOK_URL is not set")
    if not key:
        raise HTTPException(status_code=500, detail="MAKE_API_KEY is not set")
    return url, key


@router.post("/image")
def generate_images(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    UI calls this to request image generation for selected items.

    - Only items with content_type='image'
    - Allowed: TOPIC_INGESTED / REJECTED / DRAFT_READY / PENDING_APPROVAL (we will re-generate if needed)
    - We set status -> GENERATING, then send request to Make.
    - Make later calls /media/ingest to attach media_url and move to PENDING_APPROVAL.
    """
    make_url, make_key = _require_make_config()

    uuid_ids = _parse_ids(payload)

    items = db.execute(select(ContentItem).where(ContentItem.id.in_(uuid_ids))).scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    to_send: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for it in items:
        if it.content_type != "image":
            skipped.append({"id": str(it.id), "reason": f"Not an image item (content_type={it.content_type})"})
            continue

        # We will regenerate even if it was already pending, that's fine.
        # Force into GENERATING if state machine allows.
        if it.status not in ("TOPIC_INGESTED", "REJECTED", "DRAFT_READY", "PENDING_APPROVAL"):
            skipped.append({"id": str(it.id), "status": it.status, "reason": "Not allowed to generate from this state"})
            continue

        # State move: REJECTED -> GENERATING is allowed in your machine
        # TOPIC_INGESTED -> GENERATING is allowed
        # DRAFT_READY -> FAILED only (in your map), so we won't use ensure_transition for DRAFT_READY/PENDING_APPROVAL
        # We'll just set to GENERATING for regeneration.
        if it.status in ("TOPIC_INGESTED", "REJECTED"):
            ensure_transition(it.status, "GENERATING")
        it.status = "GENERATING"
        it.last_error = None
        it.updated_at = datetime.utcnow()

        # Prompt strategy (simple and reliable):
        # Use body_text if present, otherwise title, otherwise topic_id
        prompt = (it.body_text or it.title or f"Topic {it.topic_id}").strip()

        to_send.append(
            {
                "content_item_id": str(it.id),
                "brand_id": it.brand_id,
                "platform": it.platform,
                "prompt": prompt,
                # you can use this inside Make to decide size/aspect ratio:
                "aspect_hint": "square" if it.platform in ("instagram", "facebook") else "landscape",
            }
        )

    db.commit()

    if not to_send:
        return {"sent": 0, "skipped": len(skipped), "skipped_items": skipped}

    headers = {"Content-Type": "application/json", "x-make-apikey": make_key}

    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(make_url, json={"items": to_send}, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Make webhook: {e}")

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Make rejected request: {r.status_code} {r.text}")

    return {"sent": len(to_send), "skipped": len(skipped), "skipped_items": skipped}
