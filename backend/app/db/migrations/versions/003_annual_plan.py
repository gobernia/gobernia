"""annual_plans, monthly_plans, objectives + columnas en action_tasks

Revision ID: 003_annual_plan
Revises: 002_board_sessions_chat
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_annual_plan"
down_revision = "002_board_sessions_chat"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "annual_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String, nullable=False, index=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="generating"),
        sa.Column("genesis_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("board_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("diagnostico_summary", sa.Text, nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "monthly_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("annual_plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("annual_plans.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("month_index", sa.Integer, nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("focus", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="locked"),
        sa.Column("review", postgresql.JSONB, nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "objectives",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("monthly_plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("monthly_plans.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("kpi_refs", postgresql.JSONB, nullable=True),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        *_timestamps(),
    )

    # action_tasks: plan_id pasa a nullable + nuevas columnas
    op.alter_column("action_tasks", "plan_id", nullable=True)
    op.add_column("action_tasks",
                  sa.Column("objective_id", postgresql.UUID(as_uuid=True),
                            sa.ForeignKey("objectives.id", ondelete="CASCADE"), nullable=True))
    op.add_column("action_tasks", sa.Column("kpi_ref", sa.String, nullable=True))
    op.create_index("ix_action_tasks_objective_id", "action_tasks", ["objective_id"])


def downgrade() -> None:
    op.drop_index("ix_action_tasks_objective_id", table_name="action_tasks")
    op.drop_column("action_tasks", "kpi_ref")
    op.drop_column("action_tasks", "objective_id")
    op.alter_column("action_tasks", "plan_id", nullable=False)
    op.drop_table("objectives")
    op.drop_table("monthly_plans")
    op.drop_table("annual_plans")
