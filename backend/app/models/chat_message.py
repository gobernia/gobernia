import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ChatMessage(Base, UUIDMixin, TimestampMixin):
    """
    Mensaje del historial de chat de una sesión de consejo.
    role=user → mensaje del empresario
    role=assistant → respuesta de un agente de IA
    """
    __tablename__ = "chat_messages"

    board_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False)

    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant

    # Agente que responde (None cuando role=user)
    agent: Mapped[str | None] = mapped_column(String(20), nullable=True)  # CFO|CSO|CRO|Auditor

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata opcional: citations, KPIs referenciados, alertas asociadas
    message_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationship
    board_session: Mapped["BoardSession"] = relationship(back_populates="messages")
