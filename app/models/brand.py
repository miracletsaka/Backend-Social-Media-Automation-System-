import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g. "neuroflow-ai"
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g. "NeuroFlow AI"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
