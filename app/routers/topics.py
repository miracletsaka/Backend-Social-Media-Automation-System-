from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem

router = APIRouter(prefix="/topics", tags=["topics"])

  # ✅ NOT "/topics"

class CreateTopicsRequest(BaseModel):
    topics: list[str]
    brand_id: str
    platforms: list[str]
    plan_month: str          # "YYYY-MM"
    times_per_week: int

@router.post("") 
def create_topics(payload: CreateTopicsRequest, db: Session = Depends(get_db)):
    now = datetime.utcnow()

    if not payload.topics:
        raise HTTPException(status_code=400, detail="topics is required")
    if not payload.platforms:
        raise HTTPException(status_code=400, detail="platforms is required")

    created = 0

    for topic in payload.topics:
        t = (topic or "").strip()
        if not t:
            continue

        for plat in payload.platforms:
            item = ContentItem(
                id=uuid.uuid4(),
                brand_id=payload.brand_id,
                platform=plat,
                topic=t,
                plan_month=payload.plan_month,
                times_per_week=payload.times_per_week,
                status="TOPIC_INGESTED",
                created_at=now,
                updated_at=now,
            )
            db.add(item)
            created += 1

    db.commit()
    return {"content_items_created": created}
