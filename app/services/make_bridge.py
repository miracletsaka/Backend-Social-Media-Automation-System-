from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem

router = APIRouter(prefix="/make", tags=["make"])


def _parse_ids(payload: dict) -> list[uuid.UUID]:
    ids = payload.get("content_item_ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="content_item_ids is required")
    try:
        return [uuid.UUID(x) for x in ids]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid UUID(s)")


@router.post("/publish")
def send_to_make(payload: dict, db: Session = Depends(get_db)):
    """
    UI calls this to send QUEUED items to Make webhook.
    Make posts to social platforms, then calls /publishing/mark-published to confirm.
    """
    make_webhook_url = os.getenv("MAKE_WEBHOOK_URL", "").strip()
    make_api_key = os.getenv("MAKE_API_KEY", "").strip()

    if not make_webhook_url:
        raise HTTPException(status_code=500, detail="MAKE_WEBHOOK_URL is not set in backend .env")
    if not make_api_key:
        raise HTTPException(status_code=500, detail="MAKE_API_KEY is not set in backend .env")

    uuid_ids = _parse_ids(payload)

    items = db.execute(select(ContentItem).where(ContentItem.id.in_(uuid_ids))).scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    to_send: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for it in items:
        # strict: only QUEUED can be sent to Make
        if it.status != "QUEUED":
            skipped.append({"id": str(it.id), "status": it.status, "reason": "Only QUEUED items can be sent to Make"})
            continue

        caption = (it.body_text or "").strip()
        if not caption and it.content_type == "text":
            skipped.append({"id": str(it.id), "status": it.status, "reason": "No body_text to publish"})
            continue

        # ✅ For image/video require media_url
        if it.content_type in ("image", "video"):
            if not it.media_url:
                skipped.append({"id": str(it.id), "status": it.status, "reason": "Missing media_url for image/video"})
                continue

        to_send.append(
            {
                "content_item_id": str(it.id),
                "brand_id": it.brand_id,
                "platform": it.platform,
                "content_type": it.content_type,
                "caption": caption,
                "hashtags": (it.hashtags or "").strip() or None,
                "media_url": it.media_url,
                "media_type": it.media_type,
                "thumbnail_url": it.thumbnail_url,
                "scheduled_at": it.scheduled_at.isoformat() if it.scheduled_at else None,
            }
        )

    if not to_send:
        return {"sent": 0, "skipped": len(skipped), "skipped_items": skipped}

    headers = {
        "Content-Type": "application/json",
        "x-make-apikey": make_api_key,  # ✅ IMPORTANT
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(make_webhook_url, json={"items": to_send}, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Make webhook: {e}")

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Make rejected request: {r.status_code} {r.text}")

    # optional: attempt count
    now = datetime.utcnow()
    sent_ids = {x["content_item_id"] for x in to_send}
    for it in items:
        if str(it.id) in sent_ids:
            it.attempt_count = (it.attempt_count or 0) + 1
            it.updated_at = now

    db.commit()

    return {"sent": len(to_send), "skipped": len(skipped), "skipped_items": skipped}
