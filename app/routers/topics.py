# backend/app/routers/topics.py
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem

router = APIRouter(prefix="/topics", tags=["topics"])


@router.post("")
def create_topics(payload: dict, db: Session = Depends(get_db)):
    """
    Creates ContentItems for each topic x platform x content_type.

    payload:
      {
        "topics": ["..."],
        "brand_id": "neuroflow-ai",
        "platforms": ["facebook","instagram","linkedin"],
        "content_types": ["text","image","video"]
      }
    """

    topics = payload.get("topics") or []
    brand_id = (payload.get("brand_id") or "neuroflow-ai").strip()
    platforms = payload.get("platforms") or []
    content_types = payload.get("content_types") or []

    if not isinstance(topics, list) or len(topics) == 0:
        raise HTTPException(status_code=400, detail="topics must be a non-empty list")
    if not isinstance(platforms, list) or len(platforms) == 0:
        raise HTTPException(status_code=400, detail="platforms must be a non-empty list")
    if not isinstance(content_types, list) or len(content_types) == 0:
        raise HTTPException(status_code=400, detail="content_types must be a non-empty list")

    allowed_types = {"text", "image", "video"}

    for ct in content_types:
        if ct not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Invalid content_type: {ct}")

    created = 0
    now = datetime.utcnow()

    for t in topics:
        topic_text = (t or "").strip()
        if not topic_text:
            continue

        topic_id = uuid.uuid4()  # we use a UUID for topic_id grouping

        for platform in platforms:
            for ct in content_types:
                item = ContentItem(
                    topic_id=topic_id,
                    brand_id=brand_id,
                    platform=platform,
                    content_type=ct,
                    status="TOPIC_INGESTED",
                    title=topic_text[:300],
                    body_text=None,       # caption generated later
                    hashtags=None,
                    created_at=now,
                    updated_at=now,
                )

                # Media defaults (safe even if DB columns exist)
                # For image/video, set media_type early so UI can understand intent.
                if ct in ("image", "video"):
                    item.media_type = ct
                    item.media_caption = None
                    item.media_url = None
                    item.thumbnail_url = None
                    item.media_provider = None

                db.add(item)
                created += 1

    db.commit()
    return {"content_items_created": created}
