import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Document(Base, UUIDMixin, TimestampMixin):
    """
    Documento subido por el usuario.
    Puede pertenecer al onboarding (perfil base) o a una sesión de consejo específica.
    - board_session_id = None  →  documento de perfil (Etapa 7 inicial)
    - board_session_id = UUID  →  documento de periodo (subido en una BoardSession)
    """
    __tablename__ = "documents"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Nullable: solo se llena cuando el doc pertenece a una sesión de consejo
    board_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    agent_insights: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    session: Mapped["OnboardingSession"] = relationship(back_populates="documents")
    board_session: Mapped["BoardSession | None"] = relationship(back_populates="documents")
