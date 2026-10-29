"""Reglas de cobro: cupones, alta de suscripciones y su sincronización con Mercado Pago.

Tipos de cupón:
- porcentaje / monto: descuento en el cobro, en los primeros `num_cobros` cobros (o en
  todos si es None). Al agotarse, se le pide a Mercado Pago que cobre el precio regular.
- meses_gratis: acceso de cortesía por N meses, sin tarjeta.
"""
import calendar
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.cobro import Cupon, CuponCanje, Pago, PlanSuscripcion, Suscripcion
from app.services.pagos import mercadopago as mp

ESTADOS_MP = {"pending": "pendiente", "authorized": "activa", "paused": "pausada", "cancelled": "cancelada"}
_MX = ZoneInfo("America/Mexico_City")


class CuponInvalido(Exception):
    """El mensaje se le muestra tal cual al cliente."""


def normalizar_codigo(codigo: str | None) -> str:
    return (codigo or "").strip().upper()


def dinero(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _pesos(v: Decimal) -> str:
    return f"${int(v):,}" if v == v.to_integral_value() else f"${v:,.2f}"


def precio_con_cupon(precio, cupon: Cupon | None) -> Decimal:
    precio = dinero(precio)
    if cupon is None or cupon.tipo == "meses_gratis":
        return precio
    if cupon.tipo == "porcentaje":
        return dinero(precio * (100 - Decimal(cupon.valor)) / 100)
    return max(dinero(precio - Decimal(cupon.valor)), Decimal("0"))


def describir_cupon(c: Cupon) -> str:
    v = Decimal(c.valor)
    if c.tipo == "meses_gratis":
        n = int(v)
        return f"{n} {'mes' if n == 1 else 'meses'} gratis"
    base = f"{v.normalize():f}% de descuento" if c.tipo == "porcentaje" else f"{_pesos(v)} MXN de descuento"
    if c.num_cobros is None:
        return f"{base} en cada cobro"
    return f"{base} en el primer cobro" if c.num_cobros == 1 else f"{base} en los primeros {c.num_cobros} cobros"


def sumar_meses(d: datetime, meses: int) -> datetime:
    m = d.month - 1 + meses
    anio, mes = d.year + m // 12, m % 12 + 1
    return d.replace(year=anio, month=mes, day=min(d.day, calendar.monthrange(anio, mes)[1]))


def _fecha(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None


async def usos_por_cupon(db: AsyncSession) -> dict:
    filas = await db.execute(select(CuponCanje.cupon_id, func.count()).group_by(CuponCanje.cupon_id))
    return {cid: n for cid, n in filas.all()}


async def cupon_valido(db: AsyncSession, codigo: str | None, user_id: str) -> Cupon:
    cod = normalizar_codigo(codigo)
    if not cod:
        raise CuponInvalido("Escribe un código.")
    c = (await db.execute(select(Cupon).where(Cupon.codigo == cod))).scalar_one_or_none()
    if c is None or not c.activo:
        raise CuponInvalido("Este cupón no existe o ya no está activo.")
    if c.vigente_hasta and c.vigente_hasta < datetime.now(_MX).date():
        raise CuponInvalido("Este cupón ya venció.")
    if c.max_usos is not None:
        usos = await db.scalar(select(func.count()).select_from(CuponCanje).where(CuponCanje.cupon_id == c.id))
        if (usos or 0) >= c.max_usos:
            raise CuponInvalido("Este cupón ya alcanzó su límite de usos.")
    ya = await db.scalar(select(func.count()).select_from(CuponCanje).where(
        CuponCanje.cupon_id == c.id, CuponCanje.user_id == user_id))
    if ya:
        raise CuponInvalido("Ya usaste este cupón.")
    return c


async def _registrar_canje(db: AsyncSession, sus: Suscripcion, cupon_id=None) -> None:
    cupon_id = cupon_id or sus.cupon_id
    if cupon_id is None:
        return
    existe = await db.scalar(select(CuponCanje.id).where(
        CuponCanje.cupon_id == cupon_id, CuponCanje.user_id == sus.user_id))
    if existe is None:
        db.add(CuponCanje(cupon_id=cupon_id, user_id=sus.user_id, suscripcion_id=sus.id))


async def suscripcion_actual(db: AsyncSession, user_id: str) -> Suscripcion | None:
    """La que define la situación del cliente: una de pago activa o pausada gana a la
    cortesía vigente, y esta a una pendiente de pago. Si no hay ninguna, usa gratis."""
    filas = (await db.execute(
        select(Suscripcion).where(Suscripcion.user_id == user_id).order_by(Suscripcion.created_at.desc())
    )).scalars().all()
    ahora = datetime.now(timezone.utc)
    for estado in ("activa", "pausada", "cortesia", "pendiente"):
        for s in filas:
            if s.estado == estado and (estado != "cortesia" or (s.vence and s.vence > ahora)):
                return s
    return None


async def sincronizar_suscripcion(db: AsyncSession, sus: Suscripcion, datos: dict | None = None) -> Suscripcion:
    """Trae de Mercado Pago el estado real. Al quedar autorizada se gasta el cupón."""
    if not sus.mp_preapproval_id:
        return sus
    datos = datos or await mp.obtener_suscripcion(sus.mp_preapproval_id)
    estado = ESTADOS_MP.get(datos.get("status"), sus.estado)
    if estado == "activa" and sus.estado != "activa":
        await _registrar_canje(db, sus)
    sus.estado = estado
    sus.proximo_cobro = _fecha(datos.get("next_payment_date")) or sus.proximo_cobro
    if estado != "pendiente":
        sus.mp_init_point = None
    return sus


async def crear_suscripcion(
    db: AsyncSession, *, user_id: str, email: str, plan: PlanSuscripcion, cupon: Cupon | None,
) -> Suscripcion:
    if cupon is not None and cupon.tipo == "meses_gratis":
        raise CuponInvalido("Este cupón es de meses gratis: canjéalo sin elegir un plan.")
    # Una suscripción pendiente que quedó abierta se cierra antes de abrir otra, salvo
    # que en Mercado Pago ya se haya pagado (el webhook pudo no haber llegado).
    previas = (await db.execute(select(Suscripcion).where(
        Suscripcion.user_id == user_id, Suscripcion.estado.in_(("activa", "pausada", "pendiente"))
    ))).scalars().all()
    for p in previas:
        if p.estado == "pendiente":
            await sincronizar_suscripcion(db, p)
        if p.estado in ("activa", "pausada"):
            raise CuponInvalido("Ya tienes una suscripción activa.")
        p.estado = "cancelada"
        p.mp_init_point = None
        if p.mp_preapproval_id:
            try:
                await mp.cancelar_suscripcion(p.mp_preapproval_id)
            except mp.MercadoPagoError:
                pass  # una liga pendiente sin pagar no cobra nada aunque siga abierta

    precio = dinero(plan.precio)
    monto = precio_con_cupon(precio, cupon)
    if monto <= 0:
        raise CuponInvalido("Con este cupón el cobro quedaría en $0. Para dar acceso gratis usa un cupón de meses gratis.")
    con_descuento = cupon is not None and monto < precio
    sus = Suscripcion(
        user_id=user_id, email=email, plan_id=plan.id, cupon_id=cupon.id if cupon else None,
        estado="pendiente", monto=monto, monto_regular=precio, moneda=plan.moneda,
        intervalo_meses=plan.intervalo_meses,
        cobros_con_descuento=cupon.num_cobros if con_descuento else None,
    )
    datos = await mp.crear_suscripcion(
        referencia=str(sus.id), email=email, motivo=f"Gobernia — {plan.nombre}",
        monto=float(monto), moneda=plan.moneda, cada_meses=plan.intervalo_meses,
        back_url=f"{settings.FRONTEND_URL.rstrip('/')}/dashboard/suscripcion",
    )
    sus.mp_preapproval_id = str(datos["id"])
    sus.mp_init_point = datos.get("init_point")
    db.add(sus)
    return sus


async def canjear_meses_gratis(db: AsyncSession, *, user_id: str, email: str, cupon: Cupon) -> Suscripcion:
    """Acceso de cortesía sin tarjeta. Si ya tiene una vigente, los meses se suman."""
    if cupon.tipo != "meses_gratis":
        raise CuponInvalido("Este cupón es un descuento: aplícalo al elegir un plan.")
    meses = int(cupon.valor)
    ahora = datetime.now(timezone.utc)
    actual = await suscripcion_actual(db, user_id)
    if actual is not None and actual.estado in ("activa", "pausada"):
        raise CuponInvalido("Ya tienes una suscripción de pago; este cupón es para acceso sin tarjeta.")
    if actual is not None and actual.estado == "cortesia":
        actual.vence = sumar_meses(actual.vence, meses)
        sus = actual
    else:
        sus = Suscripcion(user_id=user_id, email=email, cupon_id=cupon.id, estado="cortesia",
                          vence=sumar_meses(ahora, meses))
        db.add(sus)
        await db.flush()
    await _registrar_canje(db, sus, cupon.id)
    return sus


async def registrar_cobro(db: AsyncSession, cobro: dict) -> Pago | None:
    """Guarda un cobro periódico (authorized_payment). Si es un cobro aprobado nuevo y la
    suscripción tiene descuento por tiempo limitado, descuenta uno; al agotarse, Mercado
    Pago pasa a cobrar el precio regular."""
    sus = (await db.execute(select(Suscripcion).where(
        Suscripcion.mp_preapproval_id == str(cobro.get("preapproval_id"))
    ))).scalar_one_or_none()
    if sus is None:
        return None
    mp_id = str(cobro["id"])
    pago_mp = cobro.get("payment") or {}
    estado = pago_mp.get("status") or cobro.get("status") or "desconocido"
    pago = (await db.execute(select(Pago).where(Pago.mp_id == mp_id))).scalar_one_or_none()
    ya_aprobado = pago is not None and pago.estado == "approved"
    if pago is None:
        pago = Pago(user_id=sus.user_id, suscripcion_id=sus.id, mp_id=mp_id, estado=estado,
                    monto=dinero(cobro.get("transaction_amount") or 0),
                    moneda=cobro.get("currency_id") or sus.moneda)
        db.add(pago)
    pago.estado = estado
    pago.fecha = _fecha(cobro.get("debit_date") or cobro.get("date_created")) or pago.fecha
    pago.detalle = {"status": cobro.get("status"), "payment": pago_mp, "retry_attempt": cobro.get("retry_attempt")}

    if estado == "approved" and not ya_aprobado and sus.cobros_con_descuento is not None:
        sus.cobros_con_descuento -= 1
        if sus.cobros_con_descuento <= 0:
            await mp.cambiar_monto(sus.mp_preapproval_id, float(sus.monto_regular), sus.moneda)
            sus.monto = sus.monto_regular
            sus.cobros_con_descuento = None
    return pago


# ── Para las respuestas del API ──────────────────────────────────────────────

def plan_dict(p: PlanSuscripcion) -> dict:
    return {"id": str(p.id), "nombre": p.nombre, "descripcion": p.descripcion, "precio": float(p.precio),
            "moneda": p.moneda, "intervalo_meses": p.intervalo_meses, "activo": p.activo}


def cupon_dict(c: Cupon, usos: int = 0) -> dict:
    return {"id": str(c.id), "codigo": c.codigo, "descripcion": c.descripcion, "tipo": c.tipo,
            "valor": float(c.valor), "num_cobros": c.num_cobros,
            "vigente_hasta": c.vigente_hasta.isoformat() if c.vigente_hasta else None,
            "max_usos": c.max_usos, "usos": usos, "activo": c.activo, "resumen": describir_cupon(c),
            "creado": c.created_at.isoformat() if c.created_at else None}


def suscripcion_dict(s: Suscripcion, plan: PlanSuscripcion | None = None) -> dict:
    return {"id": str(s.id), "estado": s.estado, "plan": plan.nombre if plan else None,
            "plan_id": str(s.plan_id) if s.plan_id else None, "monto": float(s.monto),
            "monto_regular": float(s.monto_regular), "moneda": s.moneda, "intervalo_meses": s.intervalo_meses,
            "cobros_con_descuento": s.cobros_con_descuento,
            "proximo_cobro": s.proximo_cobro.isoformat() if s.proximo_cobro else None,
            "vence": s.vence.isoformat() if s.vence else None, "liga_pago": s.mp_init_point,
            "creada": s.created_at.isoformat() if s.created_at else None}
