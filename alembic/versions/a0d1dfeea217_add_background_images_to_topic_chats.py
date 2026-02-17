"""add background_images to topic_chats

Revision ID: a0d1dfeea217
Revises: 1a01f2024af9
Create Date: 2026-01-29 13:25:53.717871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a0d1dfeea217'
down_revision: Union[str, Sequence[str], None] = '1a01f2024af9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "topic_chats",
        sa.Column(
            "background_images",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

def downgrade():
    op.drop_column("topic_chats", "background_images")
