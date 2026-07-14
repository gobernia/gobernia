"""Compromiso rastreable (nodo 6, Seguimiento PM).
Nace de una decisión de la Minuta o de un ACUERDO del Consejo (deliberación de una board_session)."""
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Compromiso(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "compromisos"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    # La IA propone un responsable POR ROL; el correo lo pone el dueño después → nullable.
    responsable_email: Mapped[str | None] = mapped_column(String, nullable=True)
    responsable_nombre: Mapped[str | None] = mapped_column(String, nullable=True)
    fecha_compromiso: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="abierto")
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    avances: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    source: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Acuerdos del Consejo ──────────────────────────────────────────────────
    # De qué sesión de consejo nació este acuerdo (None si viene de la minuta mensual).
    board_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    prioridad: Mapped[str] = mapped_column(String(10), nullable=False, default="media")
    # El vínculo con el Roadmap: nombre EXACTO de un pilar, o "" / None si es transversal.
    pilar: Mapped[str | None] = mapped_column(String, nullable=True)
    # Por qué el Consejo lo acordó.
    racional: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)
