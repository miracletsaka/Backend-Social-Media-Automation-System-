from datetime import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # "facebook", "instagram", "linkedin"
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # "Facebook"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
