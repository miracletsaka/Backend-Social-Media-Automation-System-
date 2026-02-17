"""v2 topic chats and drafts

Revision ID: 42ca2dc95ba0
Revises: 28854605c01a
Create Date: 2026-01-26 04:09:03.203356

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42ca2dc95ba0'
down_revision: Union[str, Sequence[str], None] = '28854605c01a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "topic_chats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", sa.String(), nullable=False, index=True),
        sa.Column("topic", sa.Text(), nullable=False),

        sa.Column("target_month", sa.String(length=7), nullable=True),  # "YYYY-MM"
        sa.Column("posts_per_week", sa.Integer(), nullable=True),

        sa.Column("timezone", sa.String(), nullable=False, server_default="Europe/London"),
        sa.Column("posting_hour_local", sa.Integer(), nullable=False, server_default="9"),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "content_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),

        sa.Column("topic_chat_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topic_chats.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("brand_id", sa.String(), nullable=False, index=True),
        sa.Column("platform", sa.String(), nullable=False, index=True),

        sa.Column("status", sa.String(), nullable=False, server_default="PENDING_APPROVAL", index=True),

        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.Text(), nullable=True),
        sa.Column("structured", postgresql.JSONB(), nullable=True),

        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

def downgrade():
    op.drop_table("content_drafts")
    op.drop_table("topic_chats")