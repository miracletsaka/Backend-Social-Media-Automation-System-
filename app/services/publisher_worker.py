from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, asc
import os

from app.models.content_item import ContentItem
from app.services.buffer_client import create_update, BufferError

RETRY_LIMIT = 3

def buffer_profile_for_platform(platform_id: str) -> str | None:
    # platform_id is now FK -> 'facebook','instagram','linkedin' etc
    # You can map platform IDs to env vars.
    if platform_id == "linkedin":
        return os.getenv("BUFFER_PROFILE_ID_LINKEDIN")
    if platform_id == "facebook":
        return os.getenv("BUFFER_PROFILE_ID_FACEBOOK")
    if platform_id == "instagram":
        return os.getenv("BUFFER_PROFILE_ID_INSTAGRAM")
    return None

def fetch_due(db: Session, limit: int = 20):
    now = datetime.now(timezone.utc)
    q = (
        select(ContentItem)
        .where(ContentItem.status == "SCHEDULED")
        .where(ContentItem.scheduled_at.isnot(None))
        .where(ContentItem.scheduled_at <= now)
        .order_by(asc(ContentItem.scheduled_at))
        .limit(limit)
    )
    return db.execute(q).scalars().all()

def publish_due(db: Session, limit: int = 20):
    due_items = fetch_due(db, limit=limit)
    published = 0
    failed = 0

    for it in due_items:
        # Text-first V1: skip image/video
        if it.content_type != "text":
            continue

        profile_id = buffer_profile_for_platform(it.platform)
        if not profile_id:
            it.last_error = f"No Buffer profile configured for platform={it.platform}"
            it.attempt_count = (it.attempt_count or 0) + 1
            if it.attempt_count >= RETRY_LIMIT:
                it.status = "FAILED"
            failed += 1
            continue

        try:
            text = (it.body_text or "").strip()
            if not text:
                raise BufferError("Empty body_text; cannot publish")

            res = create_update(profile_id=profile_id, text=text, scheduled_at_iso=it.scheduled_at.isoformat())
            # Buffer returns update id
            update_id = res.get("updates", [{}])[0].get("id") if isinstance(res.get("updates"), list) else None

            it.buffer_update_id = update_id
            it.status = "PUBLISHED"      # V1 assumption: Buffer accepted update
            it.published_at = datetime.now(timezone.utc)
            it.last_error = None
            published += 1

        except Exception as e:
            it.last_error = str(e)
            it.attempt_count = (it.attempt_count or 0) + 1
            if it.attempt_count >= RETRY_LIMIT:
                it.status = "FAILED"
            failed += 1

    db.commit()
    return {"due": len(due_items), "published": published, "failed": failed}
