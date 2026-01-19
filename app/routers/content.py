from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from app.database import get_db
from app.models.content_item import ContentItem
from app.services.state_machine import ensure_transition

router = APIRouter(prefix="/content", tags=["content"])

@router.get("/all")
def list_all(db: Session = Depends(get_db)):
    return db.execute(select(ContentItem)).scalars().all()

@router.get("/pending-approval")
def pending(db: Session = Depends(get_db)):
    return db.execute(
        select(ContentItem).where(ContentItem.status == "PENDING_APPROVAL")
    ).scalars().all()

@router.post("/{cid}/move-to-pending")
def move(cid: str, db: Session = Depends(get_db)):
    item = db.get(ContentItem, cid)
    ensure_transition(item.status, "PENDING_APPROVAL")
    item.status = "PENDING_APPROVAL"
    db.commit()
    return {"id": cid, "status": "PENDING_APPROVAL"}

@router.get("/recent")
def recent(db: Session = Depends(get_db), limit: int = Query(8, ge=1, le=50)):
    q = (
        select(ContentItem)
        .order_by(desc(ContentItem.updated_at), desc(ContentItem.created_at))
        .limit(limit)
    )
    items = db.execute(q).scalars().all()
    return items

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
