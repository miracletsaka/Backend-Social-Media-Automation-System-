# app/models/template.py
from sqlalchemy import Column, String, DateTime, Text
from datetime import datetime
from app.database import Base

class Template(Base):
    __tablename__ = "templates"

    id = Column(String, primary_key=True)
    brand_id = Column(String, index=True, nullable=True)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    shapes_json = Column(Text, nullable=False)  # JSON string
    canvas_width = Column(String, nullable=False)
    canvas_height = Column(String, nullable=False)

    background_image = Column(Text, nullable=True)
    logo_placement_json = Column(Text, nullable=True)

    thumbnail_url = Column(Text, nullable=True)
    preview_url = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # ✅
