"""Suscripción del cliente con Stripe: planes, cupones, alta, cancelación, portal y webhook.

Por ahora el cobro es opcional: nadie pierde acceso por no tener suscripción.
"""
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.models.cobro import PlanSuscripcion, Suscripcion
from app.schemas.pagos import CodigoIn, SuscribirmeIn
from app.services.pagos import cobros
from app.services.pagos import stripe_api as st

_log = logging.getLogger(__name__)

router = APIRouter()

_SIN_STRIPE = "No pudimos conectar con Stripe. Intenta de nuevo en unos minutos."

# Eventos que hay que activar en el webhook de Stripe (el panel de admin los muestra).
EVENTOS = (
    "checkout.session.completed", "checkout.session.expired",
    "customer.subscription.updated", "customer.subscription.deleted",
    "invoice.paid", "invoice.payment_failed",
)


async def _plan(db: AsyncSession, plan_id) -> PlanSuscripcion | None:
    return (await db.execute(select(PlanSuscripcion).where(PlanSuscripcion.id == plan_id))).scalar_one_or_none()


async def _salida(db: AsyncSession, sus: Suscripcion | None) -> dict | None:
    if sus is None:
        return None
    return cobros.suscripcion_dict(sus, await _plan(db, sus.plan_id) if sus.plan_id else None)


@router.get("/pagos")
async def mi_suscripcion(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Planes disponibles y la situación del cliente. Al regresar de Stripe, una
    suscripción pendiente se actualiza aquí aunque el webhook no haya llegado."""
    sus = await cobros.suscripcion_actual(db, user["sub"])
    if sus is not None and sus.estado == "pendiente" and st.configurado():
        try:
            await cobros.sincronizar_suscripcion(db, sus)
            await db.commit()
            # Si la liga caducó o se canceló, la situación del cliente es otra.
            sus = await cobros.suscripcion_actual(db, user["sub"])
        except st.StripeError as e:
            _log.warning("No se pudo sincronizar la suscripción %s: %s", sus.id, e)
    planes = (await db.execute(
        select(PlanSuscripcion).where(PlanSuscripcion.activo).order_by(PlanSuscripcion.precio)
    )).scalars().all()
    return {
        "cobros_activos": st.configurado(),
        # prueba | produccion: los clientes solo ven la suscripción con cobros reales.
        "modo": st.modo(),
        "planes": [cobros.plan_dict(p) for p in planes],
        "suscripcion": await _salida(db, sus),
    }


@router.post("/pagos/cupon")
async def revisar_cupon(body: CodigoIn, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Vista previa: qué da el cupón y, si se elige un plan, cuánto se cobraría."""
    try:
        c = await cobros.cupon_valido(db, body.codigo, user["sub"])
    except cobros.CuponInvalido as e:
        raise HTTPException(status_code=400, detail=str(e))
    out = {"codigo": c.codigo, "tipo": c.tipo, "resumen": cobros.describir_cupon(c)}
    if body.plan_id and c.tipo != "meses_gratis":
        plan = await _plan(db, body.plan_id)
        if plan is not None:
            out["precio"] = float(plan.precio)
            out["precio_final"] = float(cobros.precio_con_cupon(plan.precio, c))
    return out


@router.post("/pagos/suscribirme")
async def suscribirme(body: SuscribirmeIn, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Abre el pago de Stripe: dentro de gobernia.ai (client_secret + clave publicable) si
    se pide y hay clave publicable; si no, la liga a la página de Stripe."""
    if not st.configurado():
        raise HTTPException(status_code=409, detail="Los pagos todavía no están disponibles.")
    plan = await _plan(db, body.plan_id)
    if plan is None or not plan.activo:
        raise HTTPException(status_code=404, detail="Ese plan ya no está disponible.")
    email = str(user.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Tu cuenta no tiene correo.")
    try:
        cupon = await cobros.cupon_valido(db, body.codigo, user["sub"]) if (body.codigo or "").strip() else None
        clave = st.clave_publica() if body.incrustado else None
        sus, sesion = await cobros.crear_suscripcion(db, user_id=user["sub"], email=email, plan=plan,
                                                     cupon=cupon, incrustado=clave is not None)
    except cobros.CuponInvalido as e:
        raise HTTPException(status_code=400, detail=str(e))
    except st.StripeError as e:
        _log.error("Stripe rechazó la suscripción de %s: %s", user["sub"], e)
        raise HTTPException(status_code=502, detail=_SIN_STRIPE)
    await db.commit()
    if clave:
        return {"modo": "incrustado", "client_secret": sesion["client_secret"], "clave_publica": clave}
    return {"modo": "liga", "liga_pago": sus.liga_pago}


@router.get("/pagos/confirmacion")
async def confirmacion(session_id: str = Query(min_length=8, max_length=255),
                       user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Página de agradecimiento: confirma con Stripe que la sesión de pago de ESTE cliente
    ya se pagó (y activa la suscripción sin esperar al webhook). Lo que devuelve sirve para
    registrar la conversión una sola vez."""
    sus = (await db.execute(select(Suscripcion).where(
        Suscripcion.user_id == user["sub"], Suscripcion.stripe_checkout_id == session_id,
    ))).scalar_one_or_none()
    if sus is None:
        raise HTTPException(status_code=404, detail="No encontramos ese pago.")
    if not st.configurado():
        raise HTTPException(status_code=409, detail="Los pagos todavía no están disponibles.")
    try:
        sesion = await st.obtener_checkout(session_id)
        pagado = (sesion.get("status") == "complete"
                  and sesion.get("payment_status") in ("paid", "no_payment_required"))
        if pagado and sus.estado == "pendiente":
            await cobros.sincronizar_suscripcion(db, sus)
            await db.commit()
    except st.StripeError as e:
        _log.error("No se pudo confirmar el pago %s: %s", session_id, e)
        raise HTTPException(status_code=502, detail=_SIN_STRIPE)
    plan = await _plan(db, sus.plan_id) if sus.plan_id else None
    return {
        "pagado": pagado,
        "estado": sus.estado,
        "plan": plan.nombre if plan else None,
        "monto": (sesion.get("amount_total") or 0) / 100,
        "moneda": str(sesion.get("currency") or sus.moneda).upper(),
        "intervalo_meses": sus.intervalo_meses,
        "transaccion": session_id,
    }


@router.post("/pagos/canjear")
async def canjear(body: CodigoIn, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Canjea un cupón de meses gratis: acceso de cortesía sin tarjeta."""
    try:
        c = await cobros.cupon_valido(db, body.codigo, user["sub"])
        sus = await cobros.canjear_meses_gratis(db, user_id=user["sub"], email=str(user.get("email") or ""), cupon=c)
    except cobros.CuponInvalido as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    await db.refresh(sus)
    return {"suscripcion": await _salida(db, sus)}


@router.post("/pagos/cancelar")
async def cancelar(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Una suscripción de pago deja de renovarse y conserva el acceso hasta el fin del
    periodo pagado. Una pendiente (liga sin pagar) se cierra de inmediato."""
    sus = await cobros.suscripcion_actual(db, user["sub"])
    if sus is None or sus.estado not in ("activa", "pausada", "pendiente"):
        raise HTTPException(status_code=404, detail="No tienes una suscripción de pago.")
    try:
        if sus.stripe_subscription_id:
            await cobros.sincronizar_suscripcion(db, sus, await st.cancelar_al_final(sus.stripe_subscription_id))
        else:
            if sus.stripe_checkout_id:
                # ¿Ya pagó y el aviso no ha llegado? Entonces no se cancela nada.
                await cobros.sincronizar_suscripcion(db, sus)
            if sus.estado == "pendiente":
                if sus.stripe_checkout_id:
                    try:
                        await st.expirar_checkout(sus.stripe_checkout_id)
                    except st.StripeError:
                        pass  # ya expiró: se cancela igual
                sus.estado = "cancelada"
                sus.liga_pago = None
    except st.StripeError as e:
        _log.error("No se pudo cancelar la suscripción %s: %s", sus.id, e)
        raise HTTPException(status_code=502, detail=_SIN_STRIPE)
    await db.commit()
    await db.refresh(sus)
    return {"suscripcion": await _salida(db, sus)}


@router.post("/pagos/portal")
async def portal(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Liga al portal de Stripe: cambiar tarjeta, ver facturas."""
    sus = await cobros.suscripcion_actual(db, user["sub"])
    if sus is None or not sus.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No tienes una suscripción de pago.")
    try:
        sesion = await st.crear_portal(sus.stripe_customer_id, cobros.url_perfil("volver"))
    except st.StripeError as e:
        _log.error("No se pudo abrir el portal de Stripe de %s: %s", user["sub"], e)
        raise HTTPException(status_code=502, detail=_SIN_STRIPE)
    return {"url": sesion["url"]}


async def _suscripcion_de(db: AsyncSession, *, sub_id: str | None = None, checkout_id: str | None = None,
                          referencia: str | None = None) -> Suscripcion | None:
    condiciones = []
    if sub_id:
        condiciones.append(Suscripcion.stripe_subscription_id == sub_id)
    if checkout_id:
        condiciones.append(Suscripcion.stripe_checkout_id == checkout_id)
    try:
        if referencia:
            condiciones.append(Suscripcion.id == uuid.UUID(referencia))
    except ValueError:
        pass
    if not condiciones:
        return None
    return (await db.execute(select(Suscripcion).where(or_(*condiciones)).limit(1))).scalar_one_or_none()


@router.post("/pagos/webhook", name="webhook_stripe")
async def webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Aviso de Stripe. Con secreto configurado se valida la firma; sin él, el evento se
    vuelve a pedir a Stripe con nuestra clave, así un aviso falso no cambia nada."""
    if not st.configurado():
        return {"ok": True}
    cuerpo = await request.body()
    if settings.STRIPE_WEBHOOK_SECRET:
        if not st.firma_valida(cuerpo, request.headers.get("stripe-signature")):
            raise HTTPException(status_code=401, detail="Firma inválida.")
        try:
            evento = json.loads(cuerpo)
        except ValueError:
            raise HTTPException(status_code=400, detail="Aviso ilegible.")
    else:
        try:
            evento_id = json.loads(cuerpo).get("id")
        except (ValueError, AttributeError):
            evento_id = None
        if not evento_id:
            raise HTTPException(status_code=400, detail="Aviso ilegible.")
        try:
            evento = await st.obtener_evento(str(evento_id))
        except st.StripeError:
            raise HTTPException(status_code=401, detail="Aviso desconocido.")

    tipo = evento.get("type") or ""
    obj = (evento.get("data") or {}).get("object") or {}
    try:
        if tipo.startswith("checkout.session."):
            sus = await _suscripcion_de(db, checkout_id=obj.get("id"), referencia=obj.get("client_reference_id"))
            if sus is not None:
                await cobros.sincronizar_suscripcion(db, sus)
        elif tipo.startswith("customer.subscription."):
            sus = await _suscripcion_de(db, sub_id=obj.get("id"),
                                        referencia=(obj.get("metadata") or {}).get("suscripcion_id"))
            if sus is not None:
                sus.stripe_subscription_id = sus.stripe_subscription_id or obj.get("id")
                await cobros.sincronizar_suscripcion(db, sus)
        elif tipo == "invoice.paid":
            await cobros.registrar_pago(db, obj, "pagado")
        elif tipo == "invoice.payment_failed":
            await cobros.registrar_pago(db, obj, "fallido")
    except st.StripeError as e:
        # 5xx: Stripe reintenta el aviso más tarde.
        _log.error("Webhook de Stripe (%s %s): %s", tipo, evento.get("id"), e)
        raise HTTPException(status_code=502, detail="No se pudo leer el aviso.")
    return {"ok": True}
