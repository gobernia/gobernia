"""board_sessions and chat_messages tables

Revision ID: 002_board_sessions_chat
Revises: 001_initial
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_board_sessions_chat"
down_revision = None   # ajustar a la revisión anterior cuando se encadenen
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── board_sessions ────────────────────────────────────────────────────────
    op.create_table(
        "board_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "onboarding_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("onboarding_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", sa.String, nullable=False, index=True),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("kpi_snapshot", postgresql.JSONB, nullable=True),
        sa.Column("agent_analyses", postgresql.JSONB, nullable=True),
        sa.Column("profile_snapshot", postgresql.JSONB, nullable=True),
        sa.Column("governance_score_snapshot", sa.Float, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # ── chat_messages ─────────────────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "board_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("board_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", sa.String, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("agent", sa.String(20), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("message_metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # ── documents: agregar board_session_id opcional ──────────────────────────
    op.add_column(
        "documents",
        sa.Column(
            "board_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("board_sessions.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_documents_board_session_id", "documents", ["board_session_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_board_session_id", table_name="documents")
    op.drop_column("documents", "board_session_id")
    op.drop_table("chat_messages")
    op.drop_table("board_sessions")
