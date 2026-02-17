"""add media fields to content_drafts

Revision ID: 9169533ff729
Revises: 42ca2dc95ba0
Create Date: 2026-01-26 12:18:25.677571

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9169533ff729'
down_revision: Union[str, Sequence[str], None] = '42ca2dc95ba0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("content_drafts", sa.Column("media_type", sa.String(), nullable=True))
    op.add_column("content_drafts", sa.Column("media_url", sa.Text(), nullable=True))
    op.add_column("content_drafts", sa.Column("media_urls", sa.Text(), nullable=True))  # store JSON string
    op.add_column("content_drafts", sa.Column("thumbnail_url", sa.Text(), nullable=True))
    op.add_column("content_drafts", sa.Column("media_provider", sa.String(), nullable=True))
    op.add_column("content_drafts", sa.Column("media_caption", sa.Text(), nullable=True))

def downgrade():
    op.drop_column("content_drafts", "media_caption")
    op.drop_column("content_drafts", "media_provider")
    op.drop_column("content_drafts", "thumbnail_url")
    op.drop_column("content_drafts", "media_urls")
    op.drop_column("content_drafts", "media_url")
    op.drop_column("content_drafts", "media_type")