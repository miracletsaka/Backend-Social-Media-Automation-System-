import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base

class ContentDraft(Base):
    __tablename__ = "content_drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    topic_chat_id = Column(UUID(as_uuid=True), ForeignKey("topic_chats.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(String, nullable=False, index=True)
    platform = Column(String, nullable=False, index=True)

    status = Column(String, nullable=False, default="PENDING_APPROVAL", index=True)

    body_text = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)
    structured = Column(JSONB, nullable=True)
    media_type = Column(String, nullable=True)         # "image" | "video"
    media_url = Column(Text, nullable=True)
    media_urls = Column(Text, nullable=True)           # JSON string list
    thumbnail_url = Column(Text, nullable=True)
    media_provider = Column(String, nullable=True)     # "do_spaces"
    media_caption = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
