from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem

# import your generator service (update this import to your actual path)
from app.services.generators.structured_generator import generate_structured_post


router = APIRouter(prefix="/bulk", tags=["bulk"])


def _month_days(year: int, month: int) -> list[datetime]:
    _, last_day = calendar.monthrange(year, month)
    return [datetime(year, month, d, 9, 0, 0) for d in range(1, last_day + 1)]  # 09:00 by default


def _default_angles(topic: str) -> list[str]:
    # simple starter list: we’ll improve this later with AI-generated angles
    return [
        f"{topic} - Pain + Solution",
        f"{topic} - Before vs After",
        f"{topic} - 3 common mistakes",
        f"{topic} - How it works",
        f"{topic} - Cost saving angle",
        f"{topic} - Time saving angle",
        f"{topic} - Missed calls = lost revenue",
        f"{topic} - FAQ style",
        f"{topic} - Objection handling",
        f"{topic} - Mini case study",
    ]


@router.post("/month")
def generate_month(payload: dict, db: Session = Depends(get_db)):
    """
    Creates a month of QUEUED ContentItems for Facebook + LinkedIn.

    payload:
      {
        "brand_id": "neuroflow-marketing-automation",
        "platforms": ["facebook","linkedin"],
        "month": "2026-02",
        "topic": "AI receptionist",
        "content_types": ["text","image"],
        "posts_per_week": 5
      }
    """
    brand_id = (payload.get("brand_id") or "").strip()
    platforms = payload.get("platforms") or []
    month_str = (payload.get("month") or "").strip()
    topic = (payload.get("topic") or "").strip()
    content_types = payload.get("content_types") or ["text"]
    posts_per_week = int(payload.get("posts_per_week") or 5)

    if not brand_id:
        raise HTTPException(status_code=400, detail="brand_id is required")
    if platforms != ["facebook", "linkedin"] and set(platforms) != {"facebook", "linkedin"}:
        raise HTTPException(status_code=400, detail="platforms must be facebook + linkedin only")
    if not month_str or "-" not in month_str:
        raise HTTPException(status_code=400, detail="month must be like 'YYYY-MM'")
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")

    allowed_types = {"text", "image"}
    for ct in content_types:
        if ct not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Invalid content_type: {ct} (allowed: text,image)")

    year = int(month_str.split("-")[0])
    month = int(month_str.split("-")[1])

    days = _month_days(year, month)

    # pick weekdays only if posts_per_week < 7
    # simplest approach: schedule Mon-Fri at 09:00
    weekdays = [d for d in days if d.weekday() < 5]  # 0=Mon
    if posts_per_week >= 7:
        schedule_days = days
    else:
        schedule_days = weekdays

    # We’ll create N posts = number of schedule days (simple)
    angles = _default_angles(topic)
    now = datetime.utcnow()

    created_ids: list[str] = []
    topic_group_id = uuid.uuid4()  # groups this whole month batch

    for idx, dt in enumerate(schedule_days):
        angle = angles[idx % len(angles)]

        for platform in platforms:
            for ct in content_types:
                # generate structured content now (so it’s ready)
                structured: dict[str, Any] = generate_structured_post(
                    brand_id=brand_id,
                    platform=platform,
                    topic_text=angle,
                    content_type=ct,
                )

                item = ContentItem(
                    topic_id=topic_group_id,
                    brand_id=brand_id,
                    platform=platform,
                    content_type=ct,
                    status="QUEUED",  # ready to publish
                    scheduled_at=dt,

                    # structured fields
                    hook=structured.get("hook"),
                    subheading=structured.get("subheading"),
                    bullets=structured.get("bullets"),
                    proof=structured.get("proof"),
                    cta=structured.get("cta"),
                    structured=structured,

                    # keep legacy fields for compatibility
                    title=(structured.get("hook") or angle)[:300],
                    body_text=None,
                    hashtags=" ".join(structured.get("hashtags") or []) if isinstance(structured.get("hashtags"), list) else None,

                    created_at=now,
                    updated_at=now,
                )

                # image prompt if needed
                if ct == "image":
                    item.media_type = "image"
                    item.media_caption = None
                    item.media_url = None
                    # store prompt in structured
                    # (your image pipeline can read it later)

                db.add(item)
                db.flush()  # get id
                created_ids.append(str(item.id))

    db.commit()

    return {
        "created": len(created_ids),
        "content_item_ids": created_ids[:50],  # return first 50 to keep response small
        "note": "Items created and queued. Use /make/publish with content_item_ids to send to Buffer via Make.",
    }
