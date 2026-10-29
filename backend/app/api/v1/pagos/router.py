"""Suscripción del cliente con Mercado Pago: planes, cupones, alta, cancelación y webhook.

Por ahora el cobro es opcional: nadie pierde acceso por no tener suscripción.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.cobro import PlanSuscripcion, Suscripcion
from app.schemas.pagos import CodigoIn, SuscribirmeIn
from app.services.pagos import cobros
from app.services.pagos import mercadopago as mp

_log = logging.getLogger(__name__)

router = APIRouter()

_SIN_MP = "No pudimos conectar con Mercado Pago. Intenta de nuevo en unos minutos."


async def _plan(db: AsyncSession, plan_id) -> PlanSuscripcion | None:
    return (await db.execute(select(PlanSuscripcion).where(PlanSuscripcion.id == plan_id))).scalar_one_or_none()


async def _salida(db: AsyncSession, sus: Suscripcion | None) -> dict | None:
    if sus is None:
        return None
    return cobros.suscripcion_dict(sus, await _plan(db, sus.plan_id) if sus.plan_id else None)


@router.get("/pagos")
async def mi_suscripcion(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Planes disponibles y la situación del cliente. Al regresar de Mercado Pago, una
    suscripción pendiente se actualiza aquí aunque el webhook no haya llegado."""
    sus = await cobros.suscripcion_actual(db, user["sub"])
    if sus is not None and sus.estado == "pendiente" and mp.configurado():
        try:
            await cobros.sincronizar_suscripcion(db, sus)
            await db.commit()
            # Si la liga caducó o se canceló, la situación del cliente es otra.
            sus = await cobros.suscripcion_actual(db, user["sub"])
        except mp.MercadoPagoError as e:
            _log.warning("No se pudo sincronizar la suscripción %s: %s", sus.id, e)
    planes = (await db.execute(
        select(PlanSuscripcion).where(PlanSuscripcion.activo).order_by(PlanSuscripcion.precio)
    )).scalars().all()
    return {
        "cobros_activos": mp.configurado(),
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
    """Abre la suscripción en Mercado Pago y devuelve la liga donde el cliente paga."""
    if not mp.configurado():
        raise HTTPException(status_code=409, detail="Los pagos todavía no están disponibles.")
    plan = await _plan(db, body.plan_id)
    if plan is None or not plan.activo:
        raise HTTPException(status_code=404, detail="Ese plan ya no está disponible.")
    email = str(user.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Tu cuenta no tiene correo.")
    try:
        cupon = await cobros.cupon_valido(db, body.codigo, user["sub"]) if (body.codigo or "").strip() else None
        sus = await cobros.crear_suscripcion(db, user_id=user["sub"], email=email, plan=plan, cupon=cupon)
    except cobros.CuponInvalido as e:
        raise HTTPException(status_code=400, detail=str(e))
    except mp.MercadoPagoError as e:
        _log.error("Mercado Pago rechazó la suscripción de %s: %s", user["sub"], e)
        raise HTTPException(status_code=502, detail=_SIN_MP)
    await db.commit()
    return {"liga_pago": sus.mp_init_point}


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
    sus = await cobros.suscripcion_actual(db, user["sub"])
    if sus is None or sus.estado not in ("activa", "pausada", "pendiente"):
        raise HTTPException(status_code=404, detail="No tienes una suscripción de pago.")
    try:
        await cobros.sincronizar_suscripcion(db, sus, await mp.cancelar_suscripcion(sus.mp_preapproval_id))
    except mp.MercadoPagoError as e:
        _log.error("No se pudo cancelar la suscripción %s: %s", sus.id, e)
        raise HTTPException(status_code=502, detail=_SIN_MP)
    await db.commit()
    await db.refresh(sus)
    return {"suscripcion": await _salida(db, sus)}


@router.post("/pagos/webhook", name="webhook_mercadopago")
async def webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Aviso de Mercado Pago. Solo dice qué cambió: el dato real se lee de la API."""
    q = request.query_params
    try:
        cuerpo = await request.json()
    except ValueError:
        cuerpo = {}
    if not isinstance(cuerpo, dict):
        cuerpo = {}
    if not mp.firma_valida(request.headers.get("x-signature"), request.headers.get("x-request-id"), q.get("data.id")):
        raise HTTPException(status_code=401, detail="Firma inválida.")
    tipo = q.get("type") or q.get("topic") or cuerpo.get("type") or cuerpo.get("topic")
    data_id = q.get("data.id") or q.get("id") or str((cuerpo.get("data") or {}).get("id") or "")
    if not data_id or not mp.configurado():
        return {"ok": True}
    try:
        if tipo in ("subscription_preapproval", "preapproval"):
            sus = (await db.execute(
                select(Suscripcion).where(Suscripcion.mp_preapproval_id == data_id)
            )).scalar_one_or_none()
            if sus is not None:
                await cobros.sincronizar_suscripcion(db, sus)
        elif tipo in ("subscription_authorized_payment", "authorized_payment"):
            await cobros.registrar_cobro(db, await mp.obtener_cobro(data_id))
    except mp.MercadoPagoError as e:
        # 5xx: Mercado Pago reintenta la notificación más tarde.
        _log.error("Webhook de Mercado Pago (%s %s): %s", tipo, data_id, e)
        raise HTTPException(status_code=502, detail="No se pudo leer el aviso.")
    return {"ok": True}
