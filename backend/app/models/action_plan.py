import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ActionPlan(Base, UUIDMixin, TimestampMixin):
    """
    Plan de acción generado a partir de los análisis de los agentes
    de una sesión de consejo. Hay UN plan por board_session.
    """
    __tablename__ = "action_plans"

    board_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title:   Mapped[str] = mapped_column(Text, nullable=False)


class ActionTask(Base, UUIDMixin, TimestampMixin):
    """
    Tarea individual dentro de un ActionPlan. Editable, con estado
    Kanban (pendiente / en_progreso / completada) y prioridad.
    """
    __tablename__ = "action_tasks"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title:        Mapped[str]               = mapped_column(Text, nullable=False)
    description:  Mapped[str | None]        = mapped_column(Text, nullable=True)
    source_agent: Mapped[str | None]        = mapped_column(String, nullable=True)
    status:       Mapped[str]               = mapped_column(String, nullable=False, default="pendiente")
    priority:     Mapped[str]               = mapped_column(String, nullable=False, default="media")
    owner:        Mapped[str | None]        = mapped_column(String, nullable=True)
    due_date:     Mapped[date | None]       = mapped_column(Date, nullable=True)
    tags:         Mapped[list | None]       = mapped_column(JSONB, nullable=True, default=list)
    order_index:  Mapped[int]               = mapped_column(Integer, nullable=False, default=0)
