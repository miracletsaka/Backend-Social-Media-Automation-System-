# backend/app/routers/generation.py
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem
from app.models.content_draft import ContentDraft
from app.services.ai_generator import generate_post

router = APIRouter(prefix="/generation", tags=["generation"])

class GenerateDraftsRequest(BaseModel):
    brand_id: str
    mode: str = Field(default="new")  # "new" | "rejected" | "monthly"
    platforms: list[str] | None = None
    target_month: str | None = None
    posts_per_week: int | None = None
    brand_profile_summary: str | None = None
    brand_profile_json: object | None = None
    client_now: Optional[str] = None   # ISO string from browser
    timezone: Optional[str] = None     # "Europe/London"
    posting_hour_local: Optional[int] = 9

def _parse_iso_utc(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        iso = str(dt_str).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def _parse_client_now(client_now: Optional[str]) -> datetime:
    # default to utc now if missing
    if not client_now:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(client_now.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

def _bump_if_past(scheduled_utc: Optional[datetime], min_utc: datetime) -> Optional[datetime]:
    if not scheduled_utc:
        return None
    if scheduled_utc < min_utc:
        # bump to +60 minutes from client_now (simple V1 rule)
        return (min_utc + timedelta(minutes=60)).replace(second=0, microsecond=0)
    return scheduled_utc

@router.post("/text")
def generate_drafts(payload: GenerateDraftsRequest, db: Session = Depends(get_db)):
    now = datetime.utcnow()  # ✅ keep consistent (naive UTC)

    q = select(ContentItem).where(ContentItem.brand_id == payload.brand_id)

    if payload.platforms:
        q = q.where(ContentItem.platform.in_(payload.platforms))

    q = q.where(ContentItem.status == "TOPIC_INGESTED")

    if payload.mode == "monthly" and payload.target_month and hasattr(ContentItem, "plan_month"):
        q = q.where(ContentItem.plan_month == payload.target_month)

    items = db.execute(q).scalars().all()
    if not items:
        return {"created": 0, "generated": 0, "note": "No matching content_items found."}

    generated = 0
    failed = 0

    for it in items:
        topic_text = (getattr(it, "topic", None) or "").strip() or "Untitled topic"

        try:
            result = generate_post(
                topic_text=topic_text,
                platform=it.platform,
                brand_id=payload.brand_id,
                brand_profile_summary=payload.brand_profile_summary,
                brand_profile_json=payload.brand_profile_json,
                target_month=payload.target_month,
                posts_per_week=payload.posts_per_week,
                client_now_utc_iso=payload.client_now,
                timezone=payload.timezone or "Europe/London",
                posting_hour_local=payload.posting_hour_local or 9,
            )

            # ✅ define structured FIRST
            structured = result.get("structured") or {}

            # ✅ normalize caption
            caption = (result.get("body_text") or "").strip()

            # ✅ normalize hashtags (list or string)
            h = result.get("hashtags") or structured.get("hashtags") or ""
            if isinstance(h, list):
                hashtags = " ".join([str(x).strip() for x in h if str(x).strip()]).strip()
            else:
                hashtags = str(h).strip()

            # ✅ client now in UTC (aware)
            client_now_utc = _parse_client_now(payload.client_now)

            # ✅ scheduled_at from AI (either top-level or in structured)
            ai_scheduled = result.get("scheduled_at") or structured.get("scheduled_at")
            dt_utc = _parse_iso_utc(ai_scheduled) if ai_scheduled else None

            # ✅ bump if AI schedules in the past vs client time
            dt_utc = _bump_if_past(dt_utc, client_now_utc)

            # ✅ store naive UTC if DB column is "timestamp without time zone"
            scheduled_dt = dt_utc.replace(tzinfo=None) if dt_utc else None

            # ✅ create draft (NOW draft exists)
            draft = ContentDraft(
                id=uuid.uuid4(),
                content_item_id=it.id,
                status="PENDING_APPROVAL",
                body_text=caption or None,
                hashtags=hashtags or None,
                scheduled_at=scheduled_dt,          # ✅ uses bumped time
                structured=structured or None,
                last_error=None,
                updated_at=now,
            )
            db.add(draft)

            it.status = "HAS_DRAFT"
            it.updated_at = now

            generated += 1

        except Exception as e:
            failed += 1
            db.rollback()  # ✅ important: reset failed transaction

            # ⚠️ Only create FAILED draft if your table allows null body_text/hashtags/etc
            db.add(ContentDraft(
                id=uuid.uuid4(),
                content_item_id=it.id,
                status="FAILED",
                last_error=str(e),
                updated_at=now,
            ))

    db.commit()
    return {"created": len(items), "generated": generated, "failed": failed}
