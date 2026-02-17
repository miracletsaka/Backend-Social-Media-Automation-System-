from __future__ import annotations
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.brand_profile import BrandProfile


def get_brand_context(brand_id: str, db: Session | None = None) -> str:
    """
    Returns a plain-text brand context block for AI prompts.
    This is injected into every generation request.
    """

    close_db = False
    if db is None:
        from app.database import SessionLocal
        db = SessionLocal()
        close_db = True

    try:
        bp = db.get(BrandProfile, brand_id)
    finally:
        if close_db:
            db.close()

    if not bp:
        # Safe fallback — generation should still work
        return f"""
You are writing marketing content for a brand called "{brand_id}".
Use a professional, clear, modern tone.
""".strip()

    return f"""
You are writing marketing content for the following brand.

Brand name: {brand_id}

Website summary:
{bp.profile_summary or "N/A"}

Services:
{", ".join(bp.services or [])}

Target audience:
{", ".join(bp.audiences or [])}

Brand positioning:
{bp.positioning or "N/A"}

Tone tags:
{", ".join(bp.tone_tags or [])}

Style rules:
- Clear headings
- Short paragraphs
- Confident but not salesy
- Optimised for Facebook & LinkedIn
""".strip()
