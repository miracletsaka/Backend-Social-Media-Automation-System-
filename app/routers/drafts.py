import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from app.database import get_db
from app.models.content_draft import ContentDraft
from app.models.topic_chat import TopicChat

router = APIRouter(prefix="/drafts", tags=["drafts"])


# ---------------------------
# Helpers
# ---------------------------

def _parse_media_urls(v):
    if not v:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _draft_to_dict(d: ContentDraft, chat: TopicChat | None = None):
    return {
        "id": str(d.id),
        "topic_chat_id": str(d.topic_chat_id),

        # chat info
        "topic": chat.topic if chat else None,
        "brand_id": chat.brand_id if chat else d.brand_id,
        "target_month": chat.target_month if chat else None,
        "posts_per_week": chat.posts_per_week if chat else None,

        # draft fields
        "platform": d.platform,
        "status": d.status,
        "body_text": d.body_text,
        "hashtags": d.hashtags,
        "structured": d.structured,
        "scheduled_at": d.scheduled_at.isoformat() if d.scheduled_at else None,

        # media
        "media_type": d.media_type,
        "media_url": d.media_url,
        "media_urls": _parse_media_urls(d.media_urls),
        "thumbnail_url": d.thumbnail_url,
        "media_provider": d.media_provider,
        "media_caption": d.media_caption,

        "last_error": d.last_error,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


# ---------------------------
# 1) LIST ALL DRAFTS
# ---------------------------

@router.get("")
def list_all_drafts(
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(ContentDraft, TopicChat)
        .join(TopicChat, TopicChat.id == ContentDraft.topic_chat_id)
        .order_by(desc(ContentDraft.updated_at), desc(ContentDraft.created_at))
        .limit(limit)
    ).all()

    return [_draft_to_dict(d, chat) for d, chat in rows]


# ---------------------------
# 3) UPDATE DRAFT
# ---------------------------

@router.patch("/{draft_id}")
def update_draft(
    draft_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    draft = db.query(ContentDraft).filter(ContentDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    for key, value in payload.items():
        if hasattr(draft, key):
            setattr(draft, key, value)

    db.commit()
    db.refresh(draft)

    return {
        "ok": True,
        "id": str(draft.id),
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


# ---------------------------
# 4) ATTACH MEDIA
# ---------------------------

@router.patch("/{draft_id}/media")
def attach_media(
    draft_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    draft = db.query(ContentDraft).filter(ContentDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft.media_type = payload.get("media_type")
    draft.media_url = payload.get("media_url")
    draft.media_urls = json.dumps(payload.get("media_urls", []))
    draft.media_provider = payload.get("media_provider")
    draft.media_caption = payload.get("media_caption")

    db.commit()
    db.refresh(draft)

    return {"ok": True}


# ---------------------------
# 5) BULK REJECT
# ---------------------------

@router.post("/bulk-reject")
def bulk_reject(
    payload: dict,
    db: Session = Depends(get_db),
):
    ids = payload.get("ids", [])
    reason = payload.get("reason")

    if not ids:
        raise HTTPException(status_code=400, detail="No draft IDs provided")

    drafts = db.query(ContentDraft).filter(ContentDraft.id.in_(ids)).all()

    for d in drafts:
        d.status = "REJECTED"
        d.last_error = reason

    db.commit()

    return {"ok": True, "count": len(drafts)}

def _parse_media_urls(v):
    if not v:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []

@router.get("/{draft_id}")
def get_draft_alias(draft_id: str, db: Session = Depends(get_db)):

    print("data_id:", draft_id)
    # validate UUID
    try:
        did = uuid.UUID(draft_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid draft id")

    draft = db.execute(select(ContentDraft).where(ContentDraft.id == did)).scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    chat = db.execute(select(TopicChat).where(TopicChat.id == draft.topic_chat_id)).scalar_one_or_none()
    return _draft_to_dict(draft, chat)