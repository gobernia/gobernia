import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="CASCADE"),
        nullable=True,   # legacy: las tareas del plan anual usan objective_id
        index=True,
    )
    objective_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("objectives.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    kpi_ref: Mapped[str | None] = mapped_column(String, nullable=True)  # "impacto KPI"
    title:        Mapped[str]               = mapped_column(Text, nullable=False)
    description:  Mapped[str | None]        = mapped_column(Text, nullable=True)
    source_agent: Mapped[str | None]        = mapped_column(String, nullable=True)
    status:       Mapped[str]               = mapped_column(String, nullable=False, default="pendiente")
    priority:     Mapped[str]               = mapped_column(String, nullable=False, default="media")
    # ¿La tarea está DENTRO del plan del año? False = el usuario la dejó fuera al
    # aprobar el Plan anual: no se ejecuta ni cuenta para el avance, pero queda
    # como pendiente (puede activarla después o eliminarla).
    incluida:     Mapped[bool]              = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    # ── Campos de agenda de gobierno (revisión del cliente): cada "tarea" es
    #    funcionalmente un punto del Orden del Día del Consejo. ──
    # Consejero IA que lidera el análisis del punto (CFO|CSO|CRO|Auditor).
    lead_agent:   Mapped[str | None]        = mapped_column(String(20), nullable=True)
    # Naturaleza del punto: informacion | seguimiento | deliberacion | decision.
    agenda_type:  Mapped[str | None]        = mapped_column(String(20), nullable=True)
    # Decisión/recomendación que se espera producir en la sesión, si aplica.
    decision_expected: Mapped[str | None]   = mapped_column(Text, nullable=True)
    owner:        Mapped[str | None]        = mapped_column(String, nullable=True)
    # Correo del responsable, para enviarle el enlace a sus tareas.
    owner_email:  Mapped[str | None]        = mapped_column(String, nullable=True)
    due_date:     Mapped[date | None]       = mapped_column(Date, nullable=True)
    tags:         Mapped[list | None]       = mapped_column(JSONB, nullable=True, default=list)
    order_index:  Mapped[int]               = mapped_column(Integer, nullable=False, default=0)
    required_doc: Mapped[str | None]        = mapped_column(Text, nullable=True)
    explicacion: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Veredicto del Consejo (Auditor) sobre la evidencia de la tarea, escrito al sesionar.
    # Shape: {"estado": "validada"|"insuficiente"|"sin_revisar", "motivo": str,
    #         "validated_at": ISO, "board_session_id": uuid}. None = nunca se validó.
    validacion: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evidences: Mapped[list["Evidence"]] = relationship(
        "Evidence", cascade="all, delete-orphan", order_by="Evidence.created_at",
    )
