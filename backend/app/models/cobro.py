"""Cobros: planes con precio (editables desde el panel de super admin), cupones,
suscripciones de Mercado Pago y los cobros que Mercado Pago realiza cada periodo.

Mientras no se active el cobro obligatorio, nadie pierde acceso por no tener suscripción.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PlanSuscripcion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "planes_suscripcion"

    nombre: Mapped[str] = mapped_column(String, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="MXN")
    # Cada cuántos meses se cobra: 1 mensual, 3 trimestral, 6 semestral, 12 anual.
    intervalo_meses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)


class Cupon(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cupones"

    # Siempre en mayúsculas: el cliente lo escribe como quiera.
    codigo: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    # porcentaje | monto | meses_gratis
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    # % de descuento, pesos de descuento o número de meses gratis, según el tipo.
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # porcentaje/monto: cuántos cobros llevan el descuento (None = todos).
    num_cobros: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
    max_usos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)


class CuponCanje(Base, UUIDMixin, TimestampMixin):
    """Un uso de un cupón. Se registra cuando la suscripción queda autorizada (o al
    canjear meses gratis), no al abrir el pago: un pago abandonado no gasta el cupón."""
    __tablename__ = "cupon_canjes"
    __table_args__ = (UniqueConstraint("cupon_id", "user_id", name="uq_cupon_canje_usuario"),)

    cupon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cupones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    suscripcion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suscripciones.id", ondelete="SET NULL"), nullable=True
    )

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)


class Suscripcion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "suscripciones"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    # None en una cortesía (meses gratis sin plan de pago).
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planes_suscripcion.id", ondelete="SET NULL"), nullable=True
    )
    cupon_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cupones.id", ondelete="SET NULL"), nullable=True
    )
    # pendiente | activa | pausada | cancelada | cortesia
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    # Lo que se cobra hoy por periodo (con descuento si aplica) y el precio sin descuento.
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    monto_regular: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="MXN")
    intervalo_meses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Cobros que aún llevan descuento (None = sin fin o sin cupón). Al llegar a 0 se
    # le pide a Mercado Pago que cobre el precio regular.
    cobros_con_descuento: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mp_preapproval_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True, index=True)
    # Liga de pago de Mercado Pago mientras la suscripción está pendiente.
    mp_init_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    proximo_cobro: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Fin del acceso de cortesía.
    vence: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)


class Pago(Base, UUIDMixin, TimestampMixin):
    """Un cobro periódico de Mercado Pago (authorized_payment) de una suscripción."""
    __tablename__ = "pagos"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    suscripcion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suscripciones.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mp_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="MXN")
    # approved | rejected | pending | … (estado del pago en Mercado Pago)
    estado: Mapped[str] = mapped_column(String(30), nullable=False)
    fecha: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detalle: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)
