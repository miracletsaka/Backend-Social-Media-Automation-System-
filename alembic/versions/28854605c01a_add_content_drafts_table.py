"""add content_drafts table

Revision ID: 28854605c01a
Revises: e502173b40e6
Create Date: 2026-01-23 14:38:56.327613

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28854605c01a'
down_revision: Union[str, Sequence[str], None] = 'e502173b40e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
from sqlalchemy.dialects import postgresql

def upgrade():
    op.create_table(
        "content_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),

        sa.Column("status", sa.String(), nullable=False, server_default="PENDING_APPROVAL"),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("structured", postgresql.JSONB(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
