# backend/app/routers/planner.py
from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem
from app.services.state_machine import ensure_transition

router = APIRouter(prefix="/planner", tags=["planner"])


class AutoScheduleMonthRequest(BaseModel):
    brand_id: str
    plan_month: str  # "YYYY-MM"
    time_of_day: Optional[str] = "09:00"  # local-style "HH:MM"
    timezone: Optional[str] = None  # V1: not used, but kept for later
    dry_run: Optional[bool] = False


def _parse_plan_month(plan_month: str) -> tuple[int, int]:
    s = (plan_month or "").strip()
    if len(s) != 7 or s[4] != "-":
        raise ValueError("plan_month must be YYYY-MM")
    y = int(s[0:4])
    m = int(s[5:7])
    if m < 1 or m > 12:
        raise ValueError("Invalid month")
    return y, m


def _parse_time_of_day(t: str) -> tuple[int, int]:
    s = (t or "").strip()
    if len(s) != 5 or s[2] != ":":
        raise ValueError("time_of_day must be HH:MM")
    hh = int(s[0:2])
    mm = int(s[3:5])
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        raise ValueError("Invalid time_of_day")
    return hh, mm


def _month_date_range(year: int, month: int) -> tuple[datetime, datetime]:
    # UTC naive (your DB uses timestamp without tz)
    start = datetime(year, month, 1, 0, 0, 0)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59)
    return start, end


def _pick_weekdays(times_per_week: int) -> list[int]:
    """
    Returns list of weekday indexes (Mon=0..Sun=6)
    V1 simple distribution:
      1 -> [2] (Wed)
      2 -> [1, 3] (Tue, Thu)
      3 -> [0, 2, 4] (Mon, Wed, Fri)
      4 -> [0, 1, 3, 4]
      5 -> [0, 1, 2, 3, 4]
      6 -> [0, 1, 2, 3, 4, 5]
      7 -> [0..6]
      >7 -> still 0..6 (we’ll schedule daily in V1)
    """
    if times_per_week <= 1:
        return [2]
    if times_per_week == 2:
        return [1, 3]
    if times_per_week == 3:
        return [0, 2, 4]
    if times_per_week == 4:
        return [0, 1, 3, 4]
    if times_per_week == 5:
        return [0, 1, 2, 3, 4]
    if times_per_week == 6:
        return [0, 1, 2, 3, 4, 5]
    return [0, 1, 2, 3, 4, 5, 6]


def _build_slots_for_month(year: int, month: int, times_per_week: int, hh: int, mm: int) -> list[datetime]:
    """
    Build a list of datetime slots for the entire month using chosen weekdays.
    One slot per chosen weekday.
    """
    weekdays = _pick_weekdays(times_per_week)
    last_day = calendar.monthrange(year, month)[1]

    slots: list[datetime] = []
    for day in range(1, last_day + 1):
        d = datetime(year, month, day, hh, mm, 0)
        if d.weekday() in weekdays:
            slots.append(d)

    # If times_per_week is high and we somehow got no slots (rare), fall back daily
    if not slots:
        for day in range(1, last_day + 1):
            slots.append(datetime(year, month, day, hh, mm, 0))

    return slots


@router.post("/auto-schedule-month")
def auto_schedule_month(payload: AutoScheduleMonthRequest, db: Session = Depends(get_db)):
    """
    V1:
    - Find APPROVED items for brand_id + plan_month
    - Use each item's times_per_week (preferred), else fallback to payload default (NOT provided in V1)
    - Assign scheduled_at across month (routine)
    - Update status to SCHEDULED
    """
    brand_id = (payload.brand_id or "").strip()
    if not brand_id:
        raise HTTPException(status_code=400, detail="brand_id is required")

    try:
        year, month = _parse_plan_month(payload.plan_month)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        hh, mm = _parse_time_of_day(payload.time_of_day or "09:00")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # pull APPROVED items for that month
    q = (
        select(ContentItem)
        .where(ContentItem.brand_id == brand_id)
        .where(ContentItem.status == "APPROVED")
        .where(ContentItem.plan_month == payload.plan_month)
        .order_by(ContentItem.created_at.asc())
    )

    items = db.execute(q).scalars().all()
    if not items:
        return {"scheduled": 0, "note": "No APPROVED items found for this month."}

    # V1: assume all month items share same times_per_week.
    # If mixed, we use the first non-null. (Later we can group.)
    tpf = None
    for it in items:
        if getattr(it, "times_per_week", None):
            tpf = int(it.times_per_week)
            break
    if not tpf:
        raise HTTPException(
            status_code=400,
            detail="times_per_week is missing on content_items. Generate topics with times_per_week first.",
        )

    if tpf < 1:
        tpf = 1

    slots = _build_slots_for_month(year, month, tpf, hh, mm)

    # If more items than slots, we reuse slots by shifting times by +10 minutes blocks (no collisions)
    now = datetime.utcnow()
    scheduled_count = 0
    preview: list[dict[str, Any]] = []

    for idx, it in enumerate(items):
        base_slot = slots[idx % len(slots)]
        bump_round = idx // len(slots)
        scheduled_at = base_slot + timedelta(minutes=10 * bump_round)

        preview.append({"id": str(it.id), "scheduled_at": scheduled_at.isoformat()})

        if payload.dry_run:
            continue

        # status transition
        try:
            ensure_transition(it.status, "SCHEDULED")
        except Exception:
            # if your state machine blocks APPROVED->SCHEDULED, just set directly (V1 safe)
            pass

        it.status = "SCHEDULED"
        it.scheduled_at = scheduled_at
        it.updated_at = now

        scheduled_count += 1

    if not payload.dry_run:
        db.commit()

    return {
        "scheduled": scheduled_count,
        "brand_id": brand_id,
        "plan_month": payload.plan_month,
        "times_per_week": tpf,
        "time_of_day": payload.time_of_day,
        "dry_run": bool(payload.dry_run),
        "preview": preview[:20],  # show first 20 for sanity
    }
