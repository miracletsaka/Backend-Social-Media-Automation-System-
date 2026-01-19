# backend/app/routers/generation.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem
from app.services.ai_generator import generate_post
from app.services.state_machine import ensure_transition

router = APIRouter(prefix="/generation", tags=["generation"])


class GenerateDraftsRequest(BaseModel):
    content_item_ids: Optional[List[str]] = None
    mode: Optional[str] = None  # "rejected" | "new" | None
    platform: Optional[str] = None
    content_type: Optional[str] = None  # "text" | "image" | "video" | None
    brand_id: str = "neuroflow-ai"

    # ✅ scraped brand context
    brand_profile_summary: Optional[str] = None
    brand_profile_json: Optional[Any] = None


def _normalize_content_type(x: Optional[str]) -> Optional[str]:
    if not x:
        return None
    v = str(x).strip().lower()
    if v in ("text", "image", "video"):
        return v
    return None


@router.post("/text")  # keep same route to avoid breaking frontend
def generate_drafts(payload: GenerateDraftsRequest, db: Session = Depends(get_db)):
    wanted_type = _normalize_content_type(payload.content_type)

    q = select(ContentItem).where(ContentItem.brand_id == payload.brand_id)

    if payload.platform:
        q = q.where(ContentItem.platform == payload.platform)

    # If caller specifies a type, filter by it. Otherwise generate for all types.
    if wanted_type:
        q = q.where(ContentItem.content_type == wanted_type)
    else:
        q = q.where(ContentItem.content_type.in_(["text", "image", "video"]))

    # Select items by ids or by mode
    if payload.content_item_ids:
        q = q.where(ContentItem.id.in_(payload.content_item_ids))
    elif payload.mode == "rejected":
        q = q.where(ContentItem.status == "REJECTED")
    else:
        # default/new
        q = q.where(ContentItem.status == "TOPIC_INGESTED")

    items = db.execute(q).scalars().all()

    updated = 0
    now = datetime.utcnow()

    for it in items:
        ct = _normalize_content_type(it.content_type) or "text"

        # safety: only allow the 3 types in this flow
        if ct not in ("text", "image", "video"):
            continue

        # Move to GENERATING
        try:
            ensure_transition(it.status, "GENERATING")
        except Exception:
            # skip items in invalid state
            continue

        it.status = "GENERATING"
        it.updated_at = now
        it.last_error = None
        db.commit()

        topic_text = (it.title or "").strip() or "Untitled topic"

        try:
            result = generate_post(
                topic_text=topic_text,
                platform=it.platform,
                brand_id=payload.brand_id,
                content_type=ct,
                brand_profile_summary=payload.brand_profile_summary,
                brand_profile_json=payload.brand_profile_json,
            )

            caption = (result.get("body_text") or "").strip()
            hashtags = (result.get("hashtags") or "").strip()
            media_prompt = (result.get("media_prompt") or "").strip()

            # ✅ Store prompt INSIDE body_text for image/video
            if ct in ("image", "video") and media_prompt:
                # Keep it readable + obvious in approvals UI
                caption = (
                    f"{caption}\n\n"
                    f"---\n"
                    f"{'IMAGE_PROMPT' if ct == 'image' else 'VIDEO_PROMPT'}:\n"
                    f"{media_prompt}\n"
                ).strip()

            it.body_text = caption
            it.hashtags = hashtags or None
            it.status = "PENDING_APPROVAL"
            it.updated_at = now
            it.last_error = None
            db.commit()

            updated += 1

        except Exception as e:
            it.status = "FAILED"
            it.last_error = str(e)
            it.updated_at = now
            db.commit()

    return {"generated": updated}
