"""Reglas de cobro: cupones, alta de suscripciones y su sincronización con Stripe.

Tipos de cupón:
- porcentaje / monto: descuento en los primeros `num_cobros` cobros (o en todos si es
  None). Se traduce a un cupón de Stripe que deja de aplicar solo al cumplir su duración.
- meses_gratis: acceso de cortesía por N meses, sin tarjeta (no pasa por Stripe).
"""
import calendar
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.cobro import Cupon, CuponCanje, Pago, PlanSuscripcion, Suscripcion
from app.services.pagos import stripe_api as st

# Estado de la suscripción en Stripe → el nuestro. past_due/unpaid: el cobro falló y
# Stripe está reintentando; se muestra como pausada hasta que el cliente pague.
ESTADOS_STRIPE = {
    "incomplete": "pendiente", "trialing": "activa", "active": "activa",
    "past_due": "pausada", "unpaid": "pausada", "paused": "pausada",
    "incomplete_expired": "cancelada", "canceled": "cancelada",
}
_MX = ZoneInfo("America/Mexico_City")


class CuponInvalido(Exception):
    """El mensaje se le muestra tal cual al cliente."""


def normalizar_codigo(codigo: str | None) -> str:
    return (codigo or "").strip().upper()


def url_perfil(pago: str) -> str:
    """Mi perfil: ahí vive la suscripción del cliente. `pago`: listo (regresa de pagar) o volver."""
    return f"{settings.FRONTEND_URL.rstrip('/')}/dashboard/datos?pago={pago}"


def url_gracias() -> str:
    """Página de agradecimiento después de pagar. Stripe cambia {CHECKOUT_SESSION_ID} por
    el id de la sesión, con el que la página confirma el pago."""
    return f"{settings.FRONTEND_URL.rstrip('/')}/dashboard/gracias?session_id={{CHECKOUT_SESSION_ID}}"


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
    """Trae de Stripe el estado real. Mientras no hay suscripción en Stripe, revisa la
    página de pago (Checkout). Al quedar activa se gasta el cupón."""
    if not sus.stripe_subscription_id:
        if not sus.stripe_checkout_id:
            return sus
        sesion = await st.obtener_checkout(sus.stripe_checkout_id)
        sus.stripe_customer_id = st._id(sesion.get("customer")) or sus.stripe_customer_id
        sus.stripe_subscription_id = st._id(sesion.get("subscription"))
        if not sus.stripe_subscription_id:
            if sesion.get("status") == "expired":
                sus.estado = "cancelada"
                sus.liga_pago = None
            return sus
        datos = None
    datos = datos or await st.obtener_suscripcion(sus.stripe_subscription_id)
    estado = ESTADOS_STRIPE.get(datos.get("status"), sus.estado)
    if estado == "activa" and sus.estado != "activa":
        await _registrar_canje(db, sus)
    sus.estado = estado
    sus.stripe_customer_id = st._id(datos.get("customer")) or sus.stripe_customer_id
    fin = st.fin_del_periodo(datos)
    se_cancela = bool(datos.get("cancel_at_period_end") or datos.get("cancel_at"))
    if estado in ("activa", "pausada") and se_cancela:
        sus.vence = st.fecha(datos.get("cancel_at")) or fin
        sus.proximo_cobro = None
    elif estado in ("activa", "pausada"):
        sus.vence = None
        sus.proximo_cobro = fin
    else:
        sus.proximo_cobro = None
    # El cupón de Stripe ya terminó: lo que se cobra es el precio regular.
    if (estado in ("activa", "pausada") and sus.monto is not None and sus.monto_regular is not None
            and sus.monto < sus.monto_regular and not st.tiene_descuento(datos)):
        sus.monto = sus.monto_regular
        sus.cobros_con_descuento = None
    if estado != "pendiente":
        sus.liga_pago = None
    return sus


async def _cliente_previo(db: AsyncSession, user_id: str) -> str | None:
    """El cliente de Stripe de una suscripción anterior, para que su historial y su
    tarjeta queden en un solo lugar."""
    return await db.scalar(select(Suscripcion.stripe_customer_id).where(
        Suscripcion.user_id == user_id, Suscripcion.stripe_customer_id.is_not(None),
    ).order_by(Suscripcion.created_at.desc()).limit(1))


async def crear_suscripcion(
    db: AsyncSession, *, user_id: str, email: str, plan: PlanSuscripcion, cupon: Cupon | None,
    incrustado: bool = False,
) -> tuple[Suscripcion, dict]:
    """Abre la sesión de pago de Stripe. Devuelve la suscripción pendiente y la sesión
    (con `incrustado`, su `client_secret`; si no, su liga en `url`)."""
    if cupon is not None and cupon.tipo == "meses_gratis":
        raise CuponInvalido("Este cupón es de meses gratis: canjéalo sin elegir un plan.")
    # Una suscripción pendiente que quedó abierta se cierra antes de abrir otra, salvo
    # que en Stripe ya se haya pagado (el webhook pudo no haber llegado).
    previas = (await db.execute(select(Suscripcion).where(
        Suscripcion.user_id == user_id, Suscripcion.estado.in_(("activa", "pausada", "pendiente"))
    ))).scalars().all()
    for p in previas:
        if p.estado == "pendiente":
            await sincronizar_suscripcion(db, p)
        if p.estado in ("activa", "pausada"):
            raise CuponInvalido("Ya tienes una suscripción activa.")
        if p.estado == "pendiente" and p.stripe_checkout_id:
            try:
                await st.expirar_checkout(p.stripe_checkout_id)
            except st.StripeError:
                pass  # una liga sin pagar no cobra nada aunque siga abierta
        p.estado = "cancelada"
        p.liga_pago = None

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
    cupon_stripe = None
    if con_descuento:
        cupon_stripe = await st.crear_cupon(
            referencia=str(sus.id), nombre=cupon.codigo, tipo=cupon.tipo, valor=cupon.valor,
            moneda=plan.moneda, num_cobros=cupon.num_cobros, cada_meses=plan.intervalo_meses,
        )
    cliente = await _cliente_previo(db, user_id)
    datos = dict(
        referencia=str(sus.id), email=email, nombre=f"Gobernia — {plan.nombre}", monto=precio,
        moneda=plan.moneda, cada_meses=plan.intervalo_meses, cupon_id=cupon_stripe,
        exito_url=url_gracias(), cancelar_url=url_perfil("volver"), incrustado=incrustado,
    )
    try:
        sesion = await st.crear_checkout(cliente_id=cliente, **datos)
    except st.StripeError as e:
        # El cliente de Stripe de una suscripción anterior se borró en Stripe: paga como nuevo.
        if not cliente or "No such customer" not in str(e):
            raise
        sesion = await st.crear_checkout(cliente_id=None, **datos)
    sus.stripe_checkout_id = sesion["id"]
    sus.liga_pago = sesion.get("url")
    db.add(sus)
    return sus, sesion


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


async def registrar_pago(db: AsyncSession, factura: dict, estado: str) -> Pago | None:
    """Guarda una factura de Stripe (`estado`: pagado | fallido). Si es un pago nuevo y la
    suscripción tiene descuento por tiempo limitado, descuenta uno de los que faltan; el
    precio regular lo cobra Stripe solo cuando termina el cupón."""
    sub_id = st.suscripcion_de_factura(factura)
    if not sub_id:
        return None
    sus = (await db.execute(select(Suscripcion).where(
        Suscripcion.stripe_subscription_id == sub_id
    ))).scalar_one_or_none()
    if sus is None:
        return None
    centavos = factura.get("amount_paid") if estado == "pagado" else factura.get("amount_due")
    if not centavos:
        return None  # factura en $0 (p. ej. cambio de plan sin cargo): no es un cobro
    fid = str(factura["id"])
    pago = (await db.execute(select(Pago).where(Pago.stripe_invoice_id == fid))).scalar_one_or_none()
    ya_pagado = pago is not None and pago.estado == "pagado"
    if pago is None:
        pago = Pago(user_id=sus.user_id, suscripcion_id=sus.id, stripe_invoice_id=fid, estado=estado,
                    monto=dinero(Decimal(centavos) / 100),
                    moneda=str(factura.get("currency") or sus.moneda).upper())
        db.add(pago)
    if ya_pagado:
        return pago  # un aviso repetido o atrasado no deshace un pago
    pago.estado = estado
    pago.monto = dinero(Decimal(centavos) / 100)
    pago.fecha = st.fecha((factura.get("status_transitions") or {}).get("paid_at")) or st.fecha(factura.get("created"))
    pago.detalle = {"motivo": factura.get("billing_reason"), "intentos": factura.get("attempt_count"),
                    "factura_url": factura.get("hosted_invoice_url")}

    if estado == "pagado" and sus.cobros_con_descuento is not None:
        sus.cobros_con_descuento -= 1
        if sus.cobros_con_descuento <= 0:
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
            "vence": s.vence.isoformat() if s.vence else None, "liga_pago": s.liga_pago,
            "puede_administrar": bool(s.stripe_customer_id),
            "creada": s.created_at.isoformat() if s.created_at else None}
