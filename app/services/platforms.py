from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.platform import Platform  # your existing table

def get_enabled_platforms(db: Session, brand_id: str) -> list[str]:
    rows = db.execute(
        select(Platform.platform)
        .where(Platform.brand_id == brand_id)
        .where(Platform.is_enabled == True)
    ).all()
    return [r[0] for r in rows]
