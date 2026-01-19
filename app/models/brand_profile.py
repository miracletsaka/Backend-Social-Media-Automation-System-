from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BrandProfile(Base):
    __tablename__ = "brand_profiles"

    brand_id: Mapped[str] = mapped_column(String(100), primary_key=True)  # matches brands.id

    website_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="IDLE")  # IDLE|SCRAPING|READY|FAILED
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pages_scraped: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    profile_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    colors: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    tone_tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    services: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    positioning: Mapped[str | None] = mapped_column(Text, nullable=True)
    audiences: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    cta_examples: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    notes_manual_override: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
