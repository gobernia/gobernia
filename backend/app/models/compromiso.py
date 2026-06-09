"""Compromiso rastreable (nodo 6, Seguimiento PM). Derivado de una decisión de la Minuta."""
import uuid
from datetime import date

from sqlalchemy import Date, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Compromiso(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "compromisos"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    responsable_email: Mapped[str | None] = mapped_column(String, nullable=True)
    responsable_nombre: Mapped[str | None] = mapped_column(String, nullable=True)
    fecha_compromiso: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="abierto")
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    avances: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    source: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)
