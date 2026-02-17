import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
import calendar, math

from app.database import get_db
from app.models.topic_chat import TopicChat
from app.models.content_draft import ContentDraft
from app.services.ai_generator import generate_monthly_drafts  # new function you will add
from app.services.platforms import get_enabled_platforms       # from section 3

router = APIRouter(prefix="/topic-chats", tags=["topic-chats"])

class GenerateForChatRequest(BaseModel):
    client_now: str | None = None     # ISO string from browser
    timezone: str | None = None       # e.g. "Europe/London"
    posting_hour_local: int | None = 9
    brand_profile_summary: str | None = None
    brand_profile_json: object | None = None

def posts_in_month(target_month: str, posts_per_week: int) -> int:
    y, m = [int(x) for x in target_month.split("-")]
    days = calendar.monthrange(y, m)[1]
    weeks = math.ceil(days / 7)
    return max(1, weeks * posts_per_week)

@router.post("/{chat_id}/generate")
def generate_for_chat(chat_id: str, payload: GenerateForChatRequest, db: Session = Depends(get_db)):
    chat = db.execute(select(TopicChat).where(TopicChat.id == chat_id)).scalars().first()
    if not chat:
        raise HTTPException(status_code=404, detail="Topic chat not found")

    if not chat.target_month or not chat.posts_per_week:
        raise HTTPException(status_code=400, detail="target_month and posts_per_week are required on the topic chat")

    platforms = get_enabled_platforms(db, chat.brand_id)
    if not platforms:
        raise HTTPException(status_code=400, detail="No enabled platforms found. Enable platforms first in Platforms page.")

    n_posts = posts_in_month(chat.target_month, chat.posts_per_week)
    now = datetime.now(timezone.utc)

    created = 0
    failed = 0

    for plat in platforms:
        try:
            # returns list[dict] each dict contains body_text, hashtags, scheduled_at, structured
            drafts = generate_monthly_drafts(
                topic_text=chat.topic,
                platform=plat,
                brand_id=chat.brand_id,
                target_month=chat.target_month,
                posts_per_week=chat.posts_per_week,
                n_posts=n_posts,
                timezone=payload.timezone or chat.timezone or "Europe/London",
                posting_hour_local=payload.posting_hour_local or chat.posting_hour_local or 9,
                client_now_utc_iso=payload.client_now,
                brand_profile_summary=payload.brand_profile_summary,
                brand_profile_json=payload.brand_profile_json,
            )

            for d in drafts:
                cd = ContentDraft(
                    id=uuid.uuid4(),
                    topic_chat_id=chat.id,
                    brand_id=chat.brand_id,
                    platform=plat,
                    status="PENDING_APPROVAL",
                    body_text=(d.get("body_text") or None),
                    hashtags=(d.get("hashtags") or None),
                    scheduled_at=d.get("scheduled_dt"),     # we’ll normalize inside ai_generator
                    structured=(d.get("structured") or None),
                    last_error=None,
                    updated_at=datetime.utcnow(),
                )
                db.add(cd)
                created += 1

        except Exception as e:
            failed += 1
            db.add(ContentDraft(
                id=uuid.uuid4(),
                topic_chat_id=chat.id,
                brand_id=chat.brand_id,
                platform=plat,
                status="FAILED",
                last_error=str(e),
                updated_at=datetime.utcnow(),
            ))

    db.commit()
    return {"platforms": platforms, "planned_per_platform": n_posts, "created": created, "failed": failed}
