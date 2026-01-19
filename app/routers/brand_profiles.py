from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.brand_profile import BrandProfile
from app.services.brand_scraper import scrape_brand_site
from app.services.brand_profiler import build_brand_profile, summarize_profile

router = APIRouter(prefix="/brand-profiles", tags=["brand-profiles"])


def _get_or_create(db: Session, brand_id: str) -> BrandProfile:
    bp = db.get(BrandProfile, brand_id)
    if bp:
        return bp
    bp = BrandProfile(brand_id=brand_id, status="IDLE")
    db.add(bp)
    db.commit()
    db.refresh(bp)
    return bp


async def _run_scrape_job(brand_id: str, website_url: str, db_factory):
    """
    Runs in background after response.
    db_factory is a callable that returns a new Session.
    """
    db: Session = db_factory()
    try:
        bp = db.get(BrandProfile, brand_id)
        if not bp:
            bp = BrandProfile(brand_id=brand_id)

        bp.status = "SCRAPING"
        bp.last_error = None
        bp.website_url = website_url
        bp.updated_at = datetime.utcnow()
        db.add(bp)
        db.commit()

        # 1) scrape
        res = await scrape_brand_site(website_url)

        # 2) profile
        profile_json = build_brand_profile(res.raw_text, res.colors, website_url)
        profile_summary = summarize_profile(profile_json)

        # 3) save
        bp.pages_scraped = res.pages
        bp.raw_text = res.raw_text
        bp.colors = res.colors
        bp.profile_json = profile_json
        bp.profile_summary = profile_summary
        bp.tone_tags = profile_json.get("tone", {}).get("tags", None)
        bp.services = profile_json.get("products_services", None)
        bp.audiences = profile_json.get("audiences", None)
        bp.positioning = (profile_json.get("positioning") or {}).get("value_props", None)
        bp.cta_examples = profile_json.get("cta_style", None)

        bp.status = "READY"
        bp.last_scraped_at = datetime.utcnow()
        bp.updated_at = datetime.utcnow()
        db.add(bp)
        db.commit()

    except Exception as e:
        bp = db.get(BrandProfile, brand_id) or BrandProfile(brand_id=brand_id)
        bp.status = "FAILED"
        bp.last_error = str(e)
        bp.updated_at = datetime.utcnow()
        db.add(bp)
        db.commit()
    finally:
        db.close()


@router.post("/scrape")
def start_scrape(payload: dict, background: BackgroundTasks, db: Session = Depends(get_db)):
    brand_id = (payload.get("brand_id") or "").strip()
    website_url = (payload.get("website_url") or "").strip()

    if not brand_id:
        raise HTTPException(status_code=400, detail="brand_id is required")
    if not website_url:
        raise HTTPException(status_code=400, detail="website_url is required")

    bp = _get_or_create(db, brand_id)

    # mark as scraping immediately
    bp.website_url = website_url
    bp.status = "SCRAPING"
    bp.last_error = None
    bp.updated_at = datetime.utcnow()
    db.add(bp)
    db.commit()

    # run async job
    # IMPORTANT: use a fresh Session in background task, not the request one
    from app.database import SessionLocal
    background.add_task(_run_scrape_job, brand_id, website_url, SessionLocal)

    return {"ok": True, "brand_id": brand_id, "status": "SCRAPING"}


@router.get("/{brand_id}")
def get_profile(brand_id: str, db: Session = Depends(get_db)):
    bp = db.get(BrandProfile, brand_id)
    if not bp:
        bp = BrandProfile(brand_id=brand_id, status="IDLE")
        db.add(bp)
        db.commit()
        db.refresh(bp)

    return {
        "brand_id": bp.brand_id,
        "website_url": bp.website_url,
        "status": bp.status,
        "last_error": bp.last_error,
        "last_scraped_at": bp.last_scraped_at.isoformat() if bp.last_scraped_at else None,
        "pages_scraped": bp.pages_scraped or [],
        "profile_summary": bp.profile_summary,
        "profile_json": bp.profile_json,
        "colors": bp.colors or [],
        "tone_tags": bp.tone_tags or [],
        "services": bp.services or [],
        "audiences": bp.audiences or [],
        "notes_manual_override": bp.notes_manual_override,
    }

@router.patch("/{brand_id}")
def update_profile(brand_id: str, payload: dict, db: Session = Depends(get_db)):
    bp = _get_or_create(db, brand_id)

    # allow manual override edits
    if "notes_manual_override" in payload:
        bp.notes_manual_override = (payload.get("notes_manual_override") or "").strip() or None

    # allow overriding summary/json if you want
    if "profile_summary" in payload:
        bp.profile_summary = (payload.get("profile_summary") or "").strip() or None

    if "profile_json" in payload and isinstance(payload.get("profile_json"), dict):
        bp.profile_json = payload["profile_json"]

    bp.updated_at = datetime.utcnow()
    db.add(bp)
    db.commit()
    return {"ok": True, "brand_id": brand_id}

