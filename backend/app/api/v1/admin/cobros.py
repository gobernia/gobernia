"""Super admin: cobros (Stripe), planes con precio y cupones."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.router import require_superadmin
from app.core.config import settings
from app.core.dependencies import get_db
from app.models.cobro import Cupon, Pago, PlanSuscripcion, Suscripcion
from app.schemas.pagos import CuponIn, CuponPatch, PlanIn, PlanPatch
from app.services.pagos import cobros
from app.services.pagos import stripe_api as st
from app.api.v1.pagos.router import EVENTOS

router = APIRouter()


def _url_webhook(request: Request) -> str:
    url = str(request.url_for("webhook_stripe"))
    # Detrás del proxy de Railway llega como http; Stripe necesita https.
    if url.startswith("http://") and request.url.hostname not in ("localhost", "127.0.0.1"):
        url = "https://" + url[len("http://"):]
    return url


@router.get("/admin/cobros")
async def admin_cobros(request: Request, _: dict = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    planes = (await db.execute(select(PlanSuscripcion).order_by(PlanSuscripcion.created_at))).scalars().all()
    nombre_plan = {p.id: p.nombre for p in planes}
    usos = await cobros.usos_por_cupon(db)
    cupones = (await db.execute(select(Cupon).order_by(Cupon.created_at.desc()))).scalars().all()
    suscripciones = (await db.execute(select(Suscripcion).order_by(Suscripcion.created_at.desc()))).scalars().all()
    pagos = (await db.execute(
        select(Pago).order_by(Pago.fecha.desc().nullslast(), Pago.created_at.desc()).limit(100)
    )).scalars().all()
    empresas = {r["user_id"]: r["empresa"] for r in (await db.execute(text("""
        select distinct on (user_id) user_id, memory_buffer->'company'->>'name' as empresa
        from onboarding_sessions order by user_id, created_at desc"""))).mappings().all()}
    correo = {s.user_id: s.email for s in suscripciones}

    ahora = datetime.now(timezone.utc)
    activas = [s for s in suscripciones if s.estado == "activa"]
    aprobados = select(func.coalesce(func.sum(Pago.monto), 0)).where(Pago.estado == "pagado")
    return {
        "configurado": st.configurado(),
        # Con clave de prueba (sk_test_…) los cobros no son reales.
        "modo": st.modo(),
        "webhook_firmado": bool(settings.STRIPE_WEBHOOK_SECRET),
        "url_webhook": _url_webhook(request),
        "eventos_webhook": list(EVENTOS),
        "metricas": {
            "suscriptores_activos": len(activas),
            "cortesias_vigentes": sum(1 for s in suscripciones if s.estado == "cortesia" and s.vence and s.vence > ahora),
            # Ingreso recurrente llevado a pesos por mes (un plan anual cuenta 1/12).
            "ingreso_mensual": round(sum(float(s.monto) / s.intervalo_meses for s in activas), 2),
            "cobrado_30d": float(await db.scalar(aprobados.where(Pago.fecha >= ahora - timedelta(days=30)))),
            "cobrado_total": float(await db.scalar(aprobados)),
        },
        "planes": [cobros.plan_dict(p) for p in planes],
        "cupones": [cobros.cupon_dict(c, usos.get(c.id, 0)) for c in cupones],
        "suscripciones": [
            {**cobros.suscripcion_dict(s), "plan": nombre_plan.get(s.plan_id), "email": s.email,
             "empresa": empresas.get(s.user_id)}
            for s in suscripciones
        ],
        "pagos": [
            {"id": str(p.id), "email": correo.get(p.user_id), "empresa": empresas.get(p.user_id),
             "monto": float(p.monto), "moneda": p.moneda, "estado": p.estado,
             "fecha": (p.fecha or p.created_at).isoformat() if (p.fecha or p.created_at) else None}
            for p in pagos
        ],
    }


@router.post("/admin/planes")
async def crear_plan(body: PlanIn, _: dict = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    plan = PlanSuscripcion(**body.model_dump(exclude={"precio"}), precio=cobros.dinero(body.precio))
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return cobros.plan_dict(plan)


@router.patch("/admin/planes/{plan_id}")
async def editar_plan(plan_id: uuid.UUID, body: PlanPatch, _: dict = Depends(require_superadmin),
                      db: AsyncSession = Depends(get_db)):
    """El precio nuevo aplica a suscripciones nuevas; las vigentes conservan el suyo."""
    plan = await db.get(PlanSuscripcion, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")
    for campo, valor in body.model_dump(exclude_none=True).items():
        setattr(plan, campo, cobros.dinero(valor) if campo == "precio" else valor)
    await db.commit()
    await db.refresh(plan)
    return cobros.plan_dict(plan)


@router.post("/admin/cupones")
async def crear_cupon(body: CuponIn, _: dict = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    codigo = cobros.normalizar_codigo(body.codigo)
    if await db.scalar(select(Cupon.id).where(Cupon.codigo == codigo)) is not None:
        raise HTTPException(status_code=409, detail="Ya existe un cupón con ese código.")
    cupon = Cupon(**body.model_dump(exclude={"codigo", "valor"}), codigo=codigo, valor=cobros.dinero(body.valor))
    db.add(cupon)
    await db.commit()
    await db.refresh(cupon)
    return cobros.cupon_dict(cupon)


@router.patch("/admin/cupones/{cupon_id}")
async def editar_cupon(cupon_id: uuid.UUID, body: CuponPatch, _: dict = Depends(require_superadmin),
                       db: AsyncSession = Depends(get_db)):
    """Activar/desactivar y cambiar vigencia o límite de usos (null quita el límite)."""
    cupon = await db.get(Cupon, cupon_id)
    if cupon is None:
        raise HTTPException(status_code=404, detail="Cupón no encontrado.")
    for campo, valor in body.model_dump(exclude_unset=True).items():
        if campo == "activo" and valor is None:
            continue
        setattr(cupon, campo, valor)
    await db.commit()
    await db.refresh(cupon)
    return cobros.cupon_dict(cupon, (await cobros.usos_por_cupon(db)).get(cupon.id, 0))
