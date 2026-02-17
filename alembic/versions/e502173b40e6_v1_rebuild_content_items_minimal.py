"""v1 rebuild content_items minimal

Revision ID: e502173b40e6
Revises: 0868634ba821
Create Date: 2026-01-23 09:50:03.386217

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e502173b40e6'
down_revision: Union[str, Sequence[str], None] = '0868634ba821'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1) Create a new minimal table
    op.create_table(
        "content_items_v1",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("brand_id", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),

        # rename "title" -> "topic" for clarity (optional)
        sa.Column("topic", sa.Text(), nullable=False),

        # planning fields
        sa.Column("plan_month", sa.String(length=7), nullable=False),   # "YYYY-MM"
        sa.Column("times_per_week", sa.Integer(), nullable=False),

        sa.Column("status", sa.String(), nullable=False, server_default="TOPIC_INGESTED"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    # 2) Copy data you still want from old table (map title -> topic)
    # NOTE: this assumes old table still exists.
    op.execute("""
        INSERT INTO content_items_v1 (id, brand_id, platform, topic, plan_month, times_per_week, status, created_at, updated_at)
        SELECT
            id,
            brand_id,
            platform,
            COALESCE(title, 'Untitled topic') as topic,
            COALESCE(plan_month, to_char(now(), 'YYYY-MM')) as plan_month,
            COALESCE(times_per_week, 1) as times_per_week,
            COALESCE(status, 'TOPIC_INGESTED') as status,
            COALESCE(created_at, now()) as created_at,
            COALESCE(updated_at, now()) as updated_at
        FROM content_items;
    """)

    # 3) Drop old table
    op.drop_table("content_items")

    # 4) Rename new table to original name
    op.rename_table("content_items_v1", "content_items")


def downgrade():
    # You said remove now; downgrade would require recreating old wide table (skip)
    raise Exception("Downgrade not supported for v1 rebuild migration.")