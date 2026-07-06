"""create analyses table

Revision ID: 68c7dfd8de9e
Revises:
Create Date: 2026-07-06 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "68c7dfd8de9e"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("resume_hash", sa.String(), nullable=False),
        sa.Column("jd_hash", sa.String(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_analyses_resume_jd_hash",
        "analyses",
        ["resume_hash", "jd_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_analyses_resume_jd_hash", table_name="analyses")
    op.drop_table("analyses")
