"""diagnosticos_estrategicos table

Revision ID: 004_diagnostico
Revises: 003_annual_plan
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004_diagnostico"
down_revision = "003_annual_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnosticos_estrategicos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String, nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="generating"),
        sa.Column("content", postgresql.JSONB, nullable=True),
        sa.Column("fail_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("diagnosticos_estrategicos")
