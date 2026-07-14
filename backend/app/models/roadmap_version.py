import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class RoadmapVersion(Base, UUIDMixin, TimestampMixin):
    """Snapshot INMUTABLE de un roadmap validado.

    Cada vez que el dueño valida su roadmap se archiva aquí una versión (1, 2, 3…).
    Reabrir el roadmap NO borra la versión archivada: se trabaja sobre una nueva y,
    al validarla, se archiva la siguiente. La Biblioteca lista todas, en solo lectura.
    """
    __tablename__ = "roadmap_versions"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annual_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # El roadmap COMPLETO tal como se validó. Nunca se actualiza.
    roadmap: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
