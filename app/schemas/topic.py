from pydantic import BaseModel, Field
from typing import List

class TopicCreateRequest(BaseModel):
    topics: List[str] = Field(min_length=1)
    brand_id: str = "neuroflow-ai"
    platforms: List[str] = Field(default_factory=lambda: ["facebook", "instagram", "linkedin"])
    content_types: List[str] = Field(default_factory=lambda: ["text"])
