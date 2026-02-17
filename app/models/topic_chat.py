import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base

class TopicChat(Base):
    __tablename__ = "topic_chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id = Column(String, nullable=False, index=True)
    topic = Column(Text, nullable=False)

    background_images = Column(JSONB, nullable=False, server_default="[]")

    target_month = Column(String(7), nullable=True)      # "YYYY-MM"
    posts_per_week = Column(Integer, nullable=True)

    timezone = Column(String, nullable=False, default="Europe/London")
    posting_hour_local = Column(Integer, nullable=False, default=9)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
