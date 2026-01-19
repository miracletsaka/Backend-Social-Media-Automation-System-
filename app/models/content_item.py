import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    brand_id: Mapped[str] = mapped_column(String(100), default="neuroflow-ai")

    platform: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("platforms.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # text | image | video
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="TOPIC_INGESTED")

    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[str | None] = mapped_column(Text, nullable=True)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    buffer_update_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ✅ MEDIA SUPPORT (existing columns you already have)
    media_type: Mapped[str | None] = mapped_column(String(20), nullable=True)     # "image" | "video"
    media_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)   # main public URL
    media_urls: Mapped[str | None] = mapped_column(Text, nullable=True)          # JSON string or comma list
    media_caption: Mapped[str | None] = mapped_column(Text, nullable=True)       # caption to post

    # ✅ NEW columns (now safe because migration added them)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    media_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)  # "spaces" | "local" | etc
