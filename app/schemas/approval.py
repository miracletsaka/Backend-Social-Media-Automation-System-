from pydantic import BaseModel, Field
from typing import List, Optional

class BulkApproveRequest(BaseModel):
    content_item_ids: List[str] = Field(min_length=1)

class BulkRejectRequest(BaseModel):
    content_item_ids: List[str] = Field(min_length=1)
    reason: Optional[str] = None
