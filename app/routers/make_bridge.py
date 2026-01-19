# backend/app/routers/make_bridge.py
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any
import re
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem
from app.services.state_machine import ensure_transition

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
def publish_via_make(payload: dict, db: Session = Depends(get_db)):
    """
    UI calls this to send QUEUED items to Make webhook.
    NOW: We expect Make to respond with publish result JSON (no callback).
    """
    make_webhook_url = (os.getenv("MAKE_WEBHOOK_URL") or "").strip()
    make_api_key = (os.getenv("MAKE_API_KEY") or "").strip()

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
        if it.status != "QUEUED":
            skipped.append({"id": str(it.id), "status": it.status, "reason": "Only QUEUED items can be sent to Make"})
            continue

        ctype = (it.content_type or "").lower().strip()

        payload_item: dict[str, Any] = {
            "content_item_id": str(it.id),
            "brand_id": it.brand_id,
            "platform": it.platform,
            "content_type": it.content_type,
            "scheduled_at": it.scheduled_at.isoformat() if it.scheduled_at else None,

            "text": strip_markdown((it.body_text or "").strip()),
            "caption": strip_markdown((getattr(it, "media_caption", None) or it.body_text or "").strip()) or None,
            "hashtags": (it.hashtags or "").strip() or None,

            "media_url": getattr(it, "media_url", None),
            "media_urls": getattr(it, "media_urls", None),
            "media_type": getattr(it, "media_type", None),
            "thumbnail_url": getattr(it, "thumbnail_url", None),
        }

        if ctype == "text":
            if not payload_item["text"]:
                skipped.append({"id": str(it.id), "status": it.status, "reason": "No body_text to publish as text"})
                continue

        elif ctype in ("image", "video"):
            has_media = bool(payload_item["media_url"]) or (
                isinstance(payload_item["media_urls"], list) and len(payload_item["media_urls"]) > 0
            )
            if not has_media:
                skipped.append({"id": str(it.id), "status": it.status, "reason": f"No media_url(s) for {ctype} publish"})
                continue

            if not payload_item["media_type"]:
                payload_item["media_type"] = ctype

            if not payload_item["caption"]:
                payload_item["text"] = strip_markdown(payload_item["text"]) or None

        else:
            skipped.append({"id": str(it.id), "status": it.status, "reason": f"Unsupported content_type: {it.content_type}"})
            continue

        to_send.append(payload_item)

    if not to_send:
        return {"sent": 0, "skipped": len(skipped), "skipped_items": skipped}

    headers = {"Content-Type": "application/json", "x-make-apikey": make_api_key}

    # --- Call Make and REQUIRE a JSON response with results ---
    try:
        with httpx.Client(timeout=90.0) as client:
            r = client.post(make_webhook_url, json={"items": to_send}, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Make webhook: {e}")

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Make rejected request: {r.status_code} {r.text}")

    try:
        data = r.json()
    except Exception:
        # Make may have published successfully but returned empty/non-JSON
        db.commit()
        return {
            "sent": len(to_send),
            "skipped": len(skipped),
            "skipped_items": skipped,
            "note": "Make returned non-JSON response (publish may still be successful). No publish receipt stored.",
            "make_raw_text": (r.text or "")[:500],
        }

    results = data.get("results") or []
    results_by_id: dict[str, dict[str, Any]] = {}
    for row in results:
        cid = str(row.get("content_item_id") or "").strip()
        if cid:
            results_by_id[cid] = row

    now = datetime.utcnow()
    updated_published = 0
    updated_failed = 0
    missing_in_response: list[str] = []

    for it in items:
        sid = str(it.id)
        if sid not in {x["content_item_id"] for x in to_send}:
            continue  # skipped earlier

        row = results_by_id.get(sid)
        if not row:
            missing_in_response.append(sid)
            continue

        ok = bool(row.get("ok"))
        if ok:
            published_url = (row.get("published_url") or "").strip() or None
            # state machine safe
            try:
                ensure_transition(it.status, "PUBLISHED")
            except Exception:
                pass
            it.status = "PUBLISHED"
            it.published_url = published_url
            it.published_at = now
            it.last_error = None
            it.updated_at = now
            updated_published += 1
        else:
            err = (row.get("error") or "Publish failed").strip()
            try:
                ensure_transition(it.status, "FAILED")
            except Exception:
                pass
            it.status = "FAILED"
            it.last_error = err
            it.updated_at = now
            updated_failed += 1

        # attempt_count tracking
        if hasattr(it, "attempt_count") and it.attempt_count is not None:
            it.attempt_count += 1

    db.commit()

    return {
        "sent": len(to_send),
        "skipped": len(skipped),
        "skipped_items": skipped,
        "published": updated_published,
        "failed": updated_failed,
        "missing_in_make_response": missing_in_response,
        "make_raw": data,  # keep while debugging; remove later if you want
    }

def strip_markdown(s: str) -> str:
    if not s:
        return s
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)   # **bold**
    s = re.sub(r"\*(.*?)\*", r"\1", s)       # *italic*
    s = re.sub(r"`(.*?)`", r"\1", s)         # `code`
    return s


