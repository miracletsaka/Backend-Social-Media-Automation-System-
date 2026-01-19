from pydantic import BaseModel
from datetime import datetime
from typing import List
import uuid

class BulkScheduleRequest(BaseModel):
    content_item_ids: List[uuid.UUID]
    scheduled_at: datetime  # ISO string from UI
