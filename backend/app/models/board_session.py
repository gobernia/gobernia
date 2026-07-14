import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class BoardSession(Base, UUIDMixin, TimestampMixin):
    """
    Sesión de consejo — snapshot inmutable de un periodo.
    Se crea cada vez que el usuario abre una nueva sesión de trabajo.
    El perfil base vive en OnboardingSession; aquí se guarda la foto del periodo.
    """
    __tablename__ = "board_sessions"

    onboarding_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Periodo al que pertenece esta sesión
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12

    # Ciclo de vida
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft | active | completed

    # Snapshot de KPIs ingresados para este periodo
    kpi_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Análisis generados por cada agente (CFO, CSO, CRO, Auditor)
    agent_analyses: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Críticas del Challenger Agent (pre-mortem) por agente — no se muestran al usuario,
    # son la base de la revisión que sí se almacena en agent_analyses
    agent_critiques: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # La conclusión ÚNICA del Consejo (deliberación): {conclusion, avance_roadmap, riesgos, acuerdos}.
    # Sesiones anteriores a la deliberación la tienen en NULL: el frontend cae a agent_analyses.
    conclusion: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Copia del perfil base en el momento de crear la sesión (para histórico)
    profile_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Governance Score vigente en este periodo
    governance_score_snapshot: Mapped[float | None] = mapped_column(Float, nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    onboarding_session: Mapped["OnboardingSession"] = relationship(
        back_populates="board_sessions"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="board_session",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="board_session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
