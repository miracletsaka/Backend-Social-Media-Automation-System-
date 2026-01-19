# app/models/email_token.py (or whatever filename you use)
from __future__ import annotations

from datetime import datetime
import uuid
from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    # store HASHED token (matches your auth.py)
    token: Mapped[str] = mapped_column(String(64), primary_key=True)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

Index("ix_email_token_user_exp", EmailVerificationToken.user_id, EmailVerificationToken.expires_at)
