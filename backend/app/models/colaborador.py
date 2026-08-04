"""Colaborador (responsable de tareas) con acceso a su "escritorio" por ENLACE MÁGICO.
El dueño del plan comparte un enlace /t/{token}; el responsable ve SOLO sus tareas sin login."""
import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Colaborador(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "colaboradores"

    # Dueño del plan (el user que asigna las tareas).
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # Correo del responsable; sus tareas se resuelven por owner_email == este email.
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    nombre: Mapped[str | None] = mapped_column(String, nullable=True)
    # Enlace mágico: acceso público sin auth a /t/{token}.
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    # Historial del chat de Todd (responsable): lista de {role, content}.
    chat: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)
