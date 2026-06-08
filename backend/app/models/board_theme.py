import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class BoardTheme(Base, UUIDMixin, TimestampMixin):
    """Tema del Consejo: responsabilidad que el Consejo debe cubrir en el año.
    type: permanente (cada sesión) | cobertura (rota por frecuencia) | emergente."""
    __tablename__ = "board_themes"
    __table_args__ = (
        UniqueConstraint("annual_plan_id", "key", name="uq_board_theme_plan_key"),
    )

    annual_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annual_plans.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    key:   Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    type:  Mapped[str] = mapped_column(String(20), nullable=False)
    # 1=cada sesión, 2=bimestral, 3=trimestral, 6=semestral, 12=anual; null para emergente
    every_n_sessions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active:      Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default:  Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_index: Mapped[int]  = mapped_column(Integer, nullable=False, default=0)
