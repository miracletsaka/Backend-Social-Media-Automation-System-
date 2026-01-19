from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import select, asc
from datetime import datetime, timezone
import csv
import io
import uuid

from app.database import get_db
from app.models.content_item import ContentItem
from app.services.state_machine import ensure_transition

router = APIRouter(prefix="/export", tags=["export"])

# Buffer CSV (simple + universal)
# Columns: text, scheduled_at, platform, internal_id
@router.get("/buffer.csv")
def export_buffer_csv(
    db: Session = Depends(get_db),
    brand_id: str | None = None,
    platform: str | None = None,
    from_dt: str | None = Query(None, description="ISO datetime start"),
    to_dt: str | None = Query(None, description="ISO datetime end"),
):
    q = select(ContentItem).where(ContentItem.status == "SCHEDULED")

    if brand_id:
        q = q.where(ContentItem.brand_id == brand_id)
    if platform:
        q = q.where(ContentItem.platform == platform)

    # scheduled_at range filter (optional)
    if from_dt:
        try:
            f = datetime.fromisoformat(from_dt.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="from_dt must be ISO datetime")
        q = q.where(ContentItem.scheduled_at >= f)

    if to_dt:
        try:
            t = datetime.fromisoformat(to_dt.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="to_dt must be ISO datetime")
        q = q.where(ContentItem.scheduled_at <= t)

    q = q.order_by(asc(ContentItem.scheduled_at))
    items = db.execute(q).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["text", "scheduled_at", "platform", "internal_id"])

    for it in items:
        if it.content_type != "text":
            continue  # V1 export text only
        text = (it.body_text or "").strip()
        if not text:
            continue
        scheduled = it.scheduled_at.isoformat() if it.scheduled_at else ""
        writer.writerow([text, scheduled, it.platform, str(it.id)])

    csv_data = output.getvalue()
    filename = f"buffer_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/mark-queued")
def mark_queued(payload: dict, db: Session = Depends(get_db)):
    ids = payload.get("content_item_ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="content_item_ids is required")

    # Validate UUIDs
    try:
        uuid_ids = [uuid.UUID(x) for x in ids]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid UUID(s)")

    items = db.execute(
        select(ContentItem).where(ContentItem.id.in_(uuid_ids))
    ).scalars().all()

    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    moved = 0
    skipped = []

    for it in items:
        # ✅ strict rule: only Scheduled can become Queued
        if it.status != "SCHEDULED":
            skipped.append(
                {"id": str(it.id), "status": it.status, "reason": "Only SCHEDULED items can be queued"}
            )
            continue

        try:
            ensure_transition(it.status, "QUEUED")
        except Exception as e:
            skipped.append({"id": str(it.id), "status": it.status, "reason": str(e)})
            continue

        it.status = "QUEUED"
        moved += 1

    db.commit()

    return {
        "queued": moved,
        "skipped": len(skipped),
        "skipped_items": skipped,  # useful for frontend toast / console
    }
