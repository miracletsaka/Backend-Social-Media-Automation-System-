from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.platform import Platform  # adjust import to your project
from app.models.topic_chat import TopicChat
from app.models.content_draft import ContentDraft
from app.services.ai_generator import generate_post
from app.utils.scheduling import posts_in_month


def generate_monthly_drafts(
    *,
    db: Session,
    topic_chat_id: uuid.UUID,
    brand_id: str,
    topic: str,
    target_month: str,
    posts_per_week: int,
    brand_profile_summary: str | None = None,
    brand_profile_json: dict | None = None,
    client_now: str | None = None,          # ISO from browser
    timezone: str = "Europe/London",
    posting_hour_local: int = 9,
) -> dict:
    """
    V2: Dynamic platforms.
    Generates drafts into ContentDraft linked to TopicChat (NOT ContentItem).
    """

    # 1) load chat (optional safety)
    chat = db.execute(
        select(TopicChat).where(TopicChat.id == topic_chat_id)
    ).scalars().first()
    if not chat:
        raise ValueError("TopicChat not found")

    # 2) load ACTIVE platforms dynamically
    platforms = db.execute(
        select(Platform).where(Platform.is_active == True)  # adjust field name if needed
    ).scalars().all()

    platform_ids = [p.id for p in platforms]  # e.g. "facebook", "linkedin"
    if not platform_ids:
        return {"created": 0, "generated": 0, "failed": 0, "note": "No active platforms configured."}

    # 3) how many posts in month
    total_posts = posts_in_month(target_month, posts_per_week)

    now = datetime.utcnow()
    generated = 0
    failed = 0

    # 4) generate drafts
    # Strategy (simple V2): rotate platforms across total_posts
    for i in range(total_posts):
        plat = platform_ids[i % len(platform_ids)]

        try:
            result = generate_post(
                topic_text=topic,
                platform=plat,
                brand_id=brand_id,
                brand_profile_summary=brand_profile_summary,
                brand_profile_json=brand_profile_json,
                target_month=target_month,
                posts_per_week=posts_per_week,
                client_now_utc_iso=client_now,
                timezone=timezone,
                posting_hour_local=posting_hour_local,
            )

            caption = (result.get("body_text") or "").strip() or None
            structured = result.get("structured") or {}

            h = result.get("hashtags") or structured.get("hashtags") or ""
            if isinstance(h, list):
                hashtags = " ".join([str(x).strip() for x in h if str(x).strip()]).strip() or None
            else:
                hashtags = str(h).strip() or None

            scheduled_at = result.get("scheduled_at") or structured.get("scheduled_at")

            draft = ContentDraft(
                id=uuid.uuid4(),
                topic_chat_id=topic_chat_id,
                brand_id=brand_id,          # keep if your table has it (recommended)
                platform=plat,
                status="PENDING_APPROVAL",
                body_text=caption,
                hashtags=hashtags,
                scheduled_at=scheduled_at,  # if your model is DateTime, parse before assigning
                structured=structured or None,
                last_error=None,
                created_at=now,
                updated_at=now,
            )
            db.add(draft)
            generated += 1

        except Exception as e:
            db.add(ContentDraft(
                id=uuid.uuid4(),
                topic_chat_id=topic_chat_id,
                brand_id=brand_id,
                platform=plat,
                status="FAILED",
                last_error=str(e),
                created_at=now,
                updated_at=now,
            ))
            failed += 1

    db.commit()
    return {"created": total_posts, "generated": generated, "failed": failed, "platforms_used": platform_ids}
