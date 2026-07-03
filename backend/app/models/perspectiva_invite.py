from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PerspectivaInvite(Base, UUIDMixin, TimestampMixin):
    """Invitación a una perspectiva externa. Accesible por token público (el invitado no tiene cuenta)."""
    __tablename__ = "perspectiva_invites"

    owner_user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # empleado|directivo|socio|cliente|proveedor
    invitee_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|active|done
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
