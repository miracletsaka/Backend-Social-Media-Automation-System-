"""add plan_month and times_per_week to content_items

Revision ID: 0868634ba821
Revises: 7d9cafe19c3a
Create Date: 2026-01-22 16:48:33.514957

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0868634ba821'
down_revision: Union[str, Sequence[str], None] = '7d9cafe19c3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("content_items", sa.Column("plan_month", sa.String(length=7), nullable=True))
    op.add_column("content_items", sa.Column("times_per_week", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("content_items", "times_per_week")
    op.drop_column("content_items", "plan_month")
