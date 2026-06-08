import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Evidence(Base, UUIDMixin, TimestampMixin):
    """Evidencia que respalda un acuerdo (ActionTask). Archivo en storage."""
    __tablename__ = "evidences"

    action_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_tasks.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    filename:     Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key:       Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes:   Mapped[int] = mapped_column(Integer, nullable=False)
