from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class DiagnosticoEstrategico(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "diagnosticos_estrategicos"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generating")
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
