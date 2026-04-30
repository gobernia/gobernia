import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class OnboardingSession(Base, UUIDMixin, TimestampMixin):
    """
    Sesión de onboarding de un usuario.
    El memory_buffer es el estado acumulado de todas las etapas completadas.
    """
    __tablename__ = "onboarding_sessions"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    completed_stages: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    memory_buffer: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    governance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    documents: Mapped[list["Document"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    board_sessions: Mapped[list["BoardSession"]] = relationship(back_populates="onboarding_session", cascade="all, delete-orphan")
