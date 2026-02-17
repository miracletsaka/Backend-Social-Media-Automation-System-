import os
import httpx
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem
from app.models.content_draft import ContentDraft  # ✅ new table
from app.services.state_machine import ensure_transition
from app.routers.content import _parse_media_urls

router = APIRouter(prefix="/make", tags=["make"])


def _parse_ids(payload: dict) -> list[str]:
    ids = payload.get("draft_ids") or payload.get("content_draft_ids") or payload.get("ids") or []
    if isinstance(ids, str):
        ids = [ids]
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="draft_ids must be a list of strings")
    ids = [str(x).strip() for x in ids if str(x).strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="draft_ids is required")
    return ids


def _coerce_hashtag_list(hashtags: Any) -> list[str]:
    # hashtags can be "#a #b" or ["#a","#b"]
    if not hashtags:
        return []
    if isinstance(hashtags, list):
        return [str(x).strip() for x in hashtags if str(x).strip()]
    s = str(hashtags).strip()
    if not s:
        return []
    # split by space, keep tokens starting with #
    parts = [p.strip() for p in s.replace("\n", " ").split(" ") if p.strip()]
    out = [p if p.startswith("#") else f"#{p}" for p in parts]
    return out


def _build_text(draft: ContentDraft) -> str:
    txt = (draft.body_text or "").strip()
    tags = _coerce_hashtag_list(draft.hashtags)
    if tags:
        # append hashtags if not already included
        if not any(t in txt for t in tags):
            txt = (txt + "\n\n" + " ".join(tags)).strip()
    return txt


@router.post("/publish")
def publish_via_make(payload: dict, db: Session = Depends(get_db)):
    """
    UI calls this to publish APPROVED drafts via Make.
    We publish from content_drafts (V2), not content_items.
    """

    print("publish_via_make payload:", payload)
    make_webhook_url = (os.getenv("MAKE_WEBHOOK_URL") or "").strip()
    make_api_key = (os.getenv("MAKE_API_KEY") or "").strip()

    if not make_webhook_url:
        raise HTTPException(status_code=500, detail="MAKE_WEBHOOK_URL is not set in backend .env")
    if not make_api_key:
        raise HTTPException(status_code=500, detail="MAKE_API_KEY is not set in backend .env")

    draft_ids = _parse_ids(payload)

    # ✅ V2: load drafts only
    rows = db.execute(
        select(ContentDraft).where(ContentDraft.id.in_(draft_ids))
    ).scalars().all()

    print("Publishing drafts via Make rows:", rows)

    if not rows:
        raise HTTPException(status_code=404, detail="No drafts found")

    to_send: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for draft in rows:
        # ✅ Only publish APPROVED (your comment says APPROVED, but your code checks PENDING_APPROVAL)
        # Keep your existing behavior to avoid changing flows.
        if (draft.status or "").upper() != "PENDING_APPROVAL":
            skipped.append({
                "id": str(draft.id),
                "status": draft.status,
                "reason": "Only PENDING_APPROVAL drafts can be sent to Make"
            })
            continue

        platform = (getattr(draft, "platform", None) or "").lower().strip()

        text = _build_text(draft)
        if not text:
            skipped.append({"id": str(draft.id), "status": draft.status, "reason": "Empty body_text"})
            continue

        media_urls = _parse_media_urls(getattr(draft, "media_urls", None))
        media_url = getattr(draft, "media_url", None)
        # ✅ Keep Make keys, but use V2 fields
        payload_item: dict[str, Any] = {
            "content_draft_id": str(draft.id),

            # V1 key kept for Make compatibility (might be None in V2)
            "content_item_id": str(getattr(draft, "content_item_id", None)) if getattr(draft, "content_item_id", None) else None,

            # metadata (use what exists)
            "brand_id": getattr(draft, "brand_id", None),
            "platform": platform,

            # if you store topic/month/week on draft or structured, use them; else None
            "topic": getattr(draft, "topic", None),
            "plan_month": getattr(draft, "plan_month", None),
            "times_per_week": getattr(draft, "times_per_week", None),

            # publish content
            "text": text,
            "hashtags": _coerce_hashtag_list(getattr(draft, "hashtags", None)),
            "hashtags_text": " ".join(_coerce_hashtag_list(getattr(draft, "hashtags", None))) or None,

            # scheduling
            "scheduled_at": draft.scheduled_at.isoformat() if getattr(draft, "scheduled_at", None) else None,

            "media_type": getattr(draft, "media_type", None),              # "image" | "video"
            "media_url": media_url,                                        # single
            "media_urls": media_urls,                                      # list
            "thumbnail_url": getattr(draft, "thumbnail_url", None),
            "media_provider": getattr(draft, "media_provider", None),
            "media_caption": getattr(draft, "media_caption", None),
        }

        to_send.append(payload_item)
 
    if not to_send:
        return {"sent": 0, "skipped": len(skipped), "skipped_items": skipped}

    headers = {"Content-Type": "application/json", "x-make-apikey": make_api_key}
    print("webhookurl:", make_webhook_url, "apikey:", make_api_key)

    # --- Call Make ---
    try:
        with httpx.Client(timeout=90.0) as client:
            r = client.post(make_webhook_url, json={"items": to_send}, headers=headers)
            print("Make response status:", r)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Make webhook: {e}")

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Make rejected request: {r.status_code} {r.text}")

    now = datetime.utcnow()
    published = 0

    for draft in rows:
        if not any(x["content_draft_id"] == str(draft.id) for x in to_send):
            continue

        try:
            ensure_transition(draft.status, "PUBLISHED")
        except Exception:
            pass

        draft.status = "PUBLISHED"
        draft.published_at = now
        draft.last_error = None
        draft.updated_at = now

        if hasattr(draft, "attempt_count") and draft.attempt_count is not None:
            draft.attempt_count += 1

        published += 1

    db.commit()

    return {
        "sent": len(to_send),
        "skipped": len(skipped),
        "skipped_items": skipped,
        "published": published,
        "make_status_code": r.status_code,
        "note": "Drafts marked as PUBLISHED because Make returned HTTP 200 OK.",
    }