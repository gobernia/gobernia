from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ToddSession(Base, UUIDMixin, TimestampMixin):
    """Entrevista conversacional de onboarding con Todd: transcript + estado acumulado."""
    __tablename__ = "todd_sessions"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # messages: lista de {"role": "todd"|"user", "text": str, "options": [str]|None}
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # state: estado acumulado por Todd (company, kpis, vision, governance, areas_cubiertas, hallazgos, narrative)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
