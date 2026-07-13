from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class CompanyLogo(Base, UUIDMixin, TimestampMixin):
    """Logo de la empresa del cliente. UNO por usuario (unique).

    Se guarda en la base de datos (no en S3/Storage): los logos son pequeños
    (<= 1 MB de entrada, re-guardados como PNG de máx 600px de ancho) y así no
    dependemos de infraestructura de almacenamiento externa.
    """
    __tablename__ = "company_logos"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True, unique=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False, default="image/png")
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
