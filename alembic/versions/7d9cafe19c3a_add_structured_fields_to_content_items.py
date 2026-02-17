"""add structured fields to content_items

Revision ID: 7d9cafe19c3a
Revises: 899fe028df00
Create Date: 2026-01-21 10:16:26.513658

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7d9cafe19c3a'
down_revision: Union[str, Sequence[str], None] = '899fe028df00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("content_items", sa.Column("hook", sa.Text(), nullable=True))
    op.add_column("content_items", sa.Column("subheading", sa.Text(), nullable=True))
    op.add_column("content_items", sa.Column("bullets", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("content_items", sa.Column("proof", sa.Text(), nullable=True))
    op.add_column("content_items", sa.Column("cta", sa.Text(), nullable=True))
    op.add_column("content_items", sa.Column("structured", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

def downgrade():
    op.drop_column("content_items", "structured")
    op.drop_column("content_items", "cta")
    op.drop_column("content_items", "proof")
    op.drop_column("content_items", "bullets")
    op.drop_column("content_items", "subheading")
    op.drop_column("content_items", "hook")
