from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class ContentItemOut(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    platform: str
    content_type: str
    status: str
    body_text: Optional[str]
    scheduled_at: Optional[datetime]
    published_at: Optional[datetime]
    published_url: Optional[str]
