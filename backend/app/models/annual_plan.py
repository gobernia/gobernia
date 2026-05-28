import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AnnualPlan(Base, UUIDMixin, TimestampMixin):
    """Plan estratégico de 12 meses. UNO por empresa/usuario."""
    __tablename__ = "annual_plans"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title:   Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    # generating | active | failed | completed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generating")

    # Sesión de consejo "génesis" que guarda el diagnóstico de los 4 agentes.
    genesis_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    diagnostico_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    months: Mapped[list["MonthlyPlan"]] = relationship(
        back_populates="annual_plan",
        cascade="all, delete-orphan",
        order_by="MonthlyPlan.month_index",
    )


class MonthlyPlan(Base, UUIDMixin, TimestampMixin):
    """Un mes (1..12) dentro del plan anual."""
    __tablename__ = "monthly_plans"

    annual_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annual_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month_index:  Mapped[int] = mapped_column(Integer, nullable=False)  # 1..12
    period_year:  Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..12 calendario
    focus: Mapped[str | None] = mapped_column(Text, nullable=True)

    # locked | active | done
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="locked")

    # Reservado para el subproyecto E (revisión de fin de mes: vas bien/mal/muy mal).
    review: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    annual_plan: Mapped["AnnualPlan"] = relationship(back_populates="months")
    objectives: Mapped[list["Objective"]] = relationship(
        back_populates="monthly_plan",
        cascade="all, delete-orphan",
        order_by="Objective.order_index",
    )


class Objective(Base, UUIDMixin, TimestampMixin):
    """Objetivo estratégico de un mes. Las tareas (action_tasks) cuelgan de aquí."""
    __tablename__ = "objectives"

    monthly_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monthly_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title:       Mapped[str]        = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Lista de labels de KPIs (provenientes del onboarding/kpi_engine) que toca el objetivo.
    kpi_refs:    Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    order_index: Mapped[int]        = mapped_column(Integer, nullable=False, default=0)

    monthly_plan: Mapped["MonthlyPlan"] = relationship(back_populates="objectives")
