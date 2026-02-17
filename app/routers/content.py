from datetime import datetime
from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.content_item import ContentItem
import uuid
from app.services.state_machine import ensure_transition
from app.models.content_draft import ContentDraft
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
import json


router = APIRouter(prefix="/content", tags=["content"])

class ContentItemPatch(BaseModel):
    # editable copy fields
    hook: Optional[str] = None
    subheading: Optional[str] = None
    bullets: Optional[List[str]] = None
    proof: Optional[str] = None
    cta: Optional[str] = None

    body_text: Optional[str] = None
    hashtags: Optional[str] = None

    # scheduling
    scheduled_at: Optional[datetime] = None

    # media attachment
    media_type: Optional[str] = None  # "image" | "video"
    media_url: Optional[str] = None
    media_urls: Optional[Any] = None  # keep flexible (list or string)
    thumbnail_url: Optional[str] = None
    media_caption: Optional[str] = None
    media_provider: Optional[str] = None

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

def _serialize_content_item(it: ContentItem) -> dict:
    return {
        "id": str(it.id),
        "topic_id": str(it.topic_id) if getattr(it, "topic_id", None) else None,

        "brand_id": getattr(it, "brand_id", None),
        "platform": getattr(it, "platform", None),
        "content_type": getattr(it, "content_type", None),
        "status": getattr(it, "status", None),

        "title": getattr(it, "title", None),
        "body_text": getattr(it, "body_text", None),
        "hashtags": getattr(it, "hashtags", None),

        "scheduled_at": it.scheduled_at.isoformat() if getattr(it, "scheduled_at", None) else None,
        "published_at": it.published_at.isoformat() if getattr(it, "published_at", None) else None,
        "published_url": getattr(it, "published_url", None),

        "media_type": getattr(it, "media_type", None),
        "media_url": getattr(it, "media_url", None),
        "media_urls": _parse_media_urls(getattr(it, "media_urls", None)),
        "thumbnail_url": getattr(it, "thumbnail_url", None),
        "media_provider": getattr(it, "media_provider", None),
        "media_caption": getattr(it, "media_caption", None),

        "last_error": getattr(it, "last_error", None),
        "created_at": it.created_at.isoformat() if getattr(it, "created_at", None) else None,
        "updated_at": it.updated_at.isoformat() if getattr(it, "updated_at", None) else None,
    }


@router.get("/all")
def list_all(db: Session = Depends(get_db), limit: int = Query(500, ge=1, le=5000)):
    rows = db.execute(
        select(ContentItem).order_by(desc(ContentItem.updated_at), desc(ContentItem.created_at)).limit(limit)
    ).scalars().all()

    return [_serialize_content_item(it) for it in rows]


@router.get("/pending-approval")
def pending_approval(brand_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = (
        select(ContentDraft, ContentItem)
        .join(ContentItem, ContentItem.id == ContentDraft.content_item_id)
        .where(ContentDraft.status == "PENDING_APPROVAL")
        .order_by(ContentDraft.created_at.desc())
    )

    if brand_id:
        q = q.where(ContentItem.brand_id == brand_id)

    rows = db.execute(q).all()

    out = []
    for draft, item in rows:
        out.append({
            "draft_id": str(draft.id),
            "content_item_id": str(item.id),
            "brand_id": item.brand_id,
            "platform": item.platform,
            "topic": item.topic,
            "plan_month": item.plan_month,
            "times_per_week": item.times_per_week,
            "status": draft.status,
            "body_text": draft.body_text,
            "hashtags": draft.hashtags,
            "scheduled_at": draft.scheduled_at.isoformat() if draft.scheduled_at else None,
            "structured": draft.structured,
            "last_error": draft.last_error,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
        })
    return out

@router.post("/{cid}/move-to-pending")
def move(cid: str, db: Session = Depends(get_db)):
    item = db.get(ContentItem, cid)
    ensure_transition(item.status, "PENDING_APPROVAL")
    item.status = "PENDING_APPROVAL"
    db.commit()
    return {"id": cid, "status": "PENDING_APPROVAL"}

@router.get("/recent")
def recent(db: Session = Depends(get_db), limit: int = Query(8, ge=1, le=50)):
    rows = db.execute(
        select(ContentItem)
        .order_by(desc(ContentItem.updated_at), desc(ContentItem.created_at))
        .limit(limit)
    ).scalars().all()

    return [_serialize_content_item(it) for it in rows]


@router.get("/approved")
def approved(
    db: Session = Depends(get_db),
    brand_id: str | None = None,
    platform: str | None = None,
    content_type: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
):
    q = select(ContentItem).where(ContentItem.status == "APPROVED")

    if brand_id:
        q = q.where(ContentItem.brand_id == brand_id)

    if platform:
        q = q.where(ContentItem.platform == platform)

    if content_type:
        q = q.where(ContentItem.content_type == content_type)

    q = q.order_by(desc(ContentItem.updated_at), desc(ContentItem.created_at)).limit(limit)

    return db.execute(q).scalars().all()

@router.get("/scheduled")
def scheduled(db: Session = Depends(get_db)):
    return db.execute(
        select(ContentItem).where(ContentItem.status == "SCHEDULED")
    ).scalars().all()

@router.get("/queued")
def queued(db: Session = Depends(get_db)):
    return db.execute(
        select(ContentItem).where(ContentItem.status == "QUEUED")
    ).scalars().all()

from sqlalchemy import select, desc

@router.get("/published")
def published(db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=200)):
    q = (
        select(ContentItem)
        .where(ContentItem.status == "PUBLISHED")
        .order_by(desc(ContentItem.published_at), desc(ContentItem.updated_at))
        .limit(limit)
    )
    return db.execute(q).scalars().all()

@router.get("/failed")
def failed(db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=200)):
    q = (
        select(ContentItem)
        .where(ContentItem.status == "FAILED")
        .order_by(desc(ContentItem.updated_at), desc(ContentItem.created_at))
        .limit(limit)
    )
    return db.execute(q).scalars().all()

@router.patch("/{content_item_id}")
def patch_content_item(
    content_item_id: str,
    payload: ContentItemPatch,
    db: Session = Depends(get_db),
):
    # 1) load
    it = db.execute(select(ContentItem).where(ContentItem.id == content_item_id)).scalars().first()
    if not it:
        raise HTTPException(status_code=404, detail="Content item not found")

    # 2) apply edits (only if provided)
    def clean_text(x: Optional[str]) -> Optional[str]:
        if x is None:
            return None
        v = x.strip()
        return v if v else None

    if payload.hook is not None:
        it.hook = clean_text(payload.hook)

    if payload.subheading is not None:
        it.subheading = clean_text(payload.subheading)

    if payload.bullets is not None:
        # keep only non-empty strings
        bullets = [str(b).strip() for b in payload.bullets if str(b).strip()]
        # optional: cap to 10 for safety
        it.bullets = bullets[:10] if bullets else None

    if payload.proof is not None:
        it.proof = clean_text(payload.proof)

    if payload.cta is not None:
        it.cta = clean_text(payload.cta)

    if payload.body_text is not None:
        it.body_text = clean_text(payload.body_text)

    if payload.hashtags is not None:
        it.hashtags = clean_text(payload.hashtags)

    if payload.scheduled_at is not None:
        it.scheduled_at = payload.scheduled_at

    # media fields
    if payload.media_type is not None:
        mt = (payload.media_type or "").strip().lower() or None
        if mt not in (None, "image", "video"):
            raise HTTPException(status_code=400, detail="media_type must be 'image' or 'video'")
        it.media_type = mt

    if payload.media_url is not None:
        it.media_url = clean_text(payload.media_url)

    if payload.media_urls is not None:
        # allow list or string
        it.media_urls = payload.media_urls

    if payload.thumbnail_url is not None:
        it.thumbnail_url = clean_text(payload.thumbnail_url)

    if payload.media_caption is not None:
        it.media_caption = clean_text(payload.media_caption)

    if payload.media_provider is not None:
        it.media_provider = clean_text(payload.media_provider)

    it.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(it)

    # return minimal fields used by UI
    return {
        "ok": True,
        "id": str(it.id),
        "updated_at": it.updated_at.isoformat() if it.updated_at else None,
    }

class UpdateMediaRequest(BaseModel):
    media_type: Optional[str] = None  # "image" | "video"
    media_url: Optional[str] = None
    media_urls: Optional[List[str]] = None
    thumbnail_url: Optional[str] = None
    media_provider: Optional[str] = "do_spaces"
    media_caption: Optional[str] = None


class UpdateMediaRequest(BaseModel):
    media_type: Optional[str] = None  # "image" | "video"
    media_url: Optional[str] = None
    media_urls: Optional[List[str]] = None
    thumbnail_url: Optional[str] = None
    media_provider: Optional[str] = "do_spaces"
    media_caption: Optional[str] = None


@router.patch("/{content_item_id}/media")
def update_content_media(content_item_id: str, payload: UpdateMediaRequest, db: Session = Depends(get_db)):
    """
    ✅ Backwards compatible:
    - If content_item_id matches a ContentItem -> update ContentItem media
    - Else if it matches a ContentDraft -> update ContentDraft media
    This lets the UI keep calling the SAME endpoint for drafts too.
    """
    print("payload:", payload)
    # validate media_type if provided
    if payload.media_type and payload.media_type not in ("image", "video"):
        raise HTTPException(status_code=400, detail="media_type must be 'image' or 'video'")

    if payload.media_url is None and (payload.media_urls is None or len(payload.media_urls) == 0):
        raise HTTPException(status_code=400, detail="Provide media_url or media_urls")

    # 1) try ContentItem first (original behavior)
    it = db.execute(select(ContentItem).where(ContentItem.id == content_item_id)).scalar_one_or_none()
    entity = it
    entity_type = "content_item"

    # 2) fallback to ContentDraft (so same route works for drafts)
    if not entity:
        dr = db.execute(select(ContentDraft).where(ContentDraft.id == content_item_id)).scalar_one_or_none()
        if not dr:
            raise HTTPException(status_code=404, detail="Content item OR draft not found")
        entity = dr
        entity_type = "content_draft"

    # ✅ apply updates to whichever entity we found
    if payload.media_type is not None:
        entity.media_type = payload.media_type

    if payload.media_urls is not None:
        entity.media_urls = json.dumps(payload.media_urls)

    if payload.media_url is not None:
        entity.media_url = payload.media_url

    if payload.thumbnail_url is not None:
        entity.thumbnail_url = payload.thumbnail_url

    if payload.media_provider is not None:
        entity.media_provider = payload.media_provider

    if payload.media_caption is not None:
        entity.media_caption = payload.media_caption

    entity.updated_at = datetime.utcnow()
    db.commit()

    return {
        "ok": True,
        "entity_type": entity_type,
        "id": str(entity.id),
        "media_url": entity.media_url,
        "media_urls": entity.media_urls,
        "media_type": getattr(entity, "media_type", None),
        "thumbnail_url": getattr(entity, "thumbnail_url", None),
        "media_provider": getattr(entity, "media_provider", None),
        "media_caption": getattr(entity, "media_caption", None),
    }
