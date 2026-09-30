"""Panel de super admin (solo lectura): usuarios registrados, en qué etapa va cada uno y
actividad de la plataforma. Acceso restringido a settings.SUPERADMIN_EMAILS.

Aún no hay cobros: cuando exista la pasarela de pago, aquí se agregan suscripciones y ventas.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db

router = APIRouter()

# Etapas del recorrido del cliente, en orden (el embudo del panel).
ETAPAS = [
    ("registrado", "Registrado"),
    ("onboarding", "Onboarding con Todd"),
    ("diagnostico", "Diagnóstico"),
    ("estrategia", "Estrategia en borrador"),
    ("estrategia_validada", "Estrategia validada"),
    ("plan_aprobado", "Plan anual aprobado"),
    ("sesionando", "Sesionando con el Consejo"),
]


def es_superadmin(user: dict) -> bool:
    email = str(user.get("email") or "").strip().lower()
    return bool(email) and email in {e.strip().lower() for e in settings.SUPERADMIN_EMAILS}


async def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    if not es_superadmin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo para super admin.")
    return user


@router.get("/admin/me")
async def admin_me(user: dict = Depends(get_current_user)):
    """Para el menú: ¿este usuario ve el panel de admin?"""
    return {"es_admin": es_superadmin(user)}


async def _filas(db: AsyncSession, sql: str) -> list:
    return list((await db.execute(text(sql))).mappings().all())


async def _usuarios(db: AsyncSession) -> list[dict]:
    users = await _filas(db, """
        select id::text as id, email, created_at, last_sign_in_at
        from auth.users order by created_at desc""")
    todd = {r["user_id"]: r for r in await _filas(db, """
        select distinct on (user_id) user_id, status from todd_sessions
        order by user_id, created_at desc""")}
    onb = {r["user_id"]: r for r in await _filas(db, """
        select distinct on (user_id) user_id, completed_stages,
               memory_buffer->'company'->>'name' as empresa,
               memory_buffer->'company'->>'industry' as industria
        from onboarding_sessions order by user_id, created_at desc""")}
    diag = {r["user_id"]: r for r in await _filas(db, """
        select distinct on (user_id) user_id, status from diagnosticos_estrategicos
        order by user_id, created_at desc""")}
    plan = {r["user_id"]: r for r in await _filas(db, """
        select distinct on (user_id) user_id, id, status, roadmap_status, periodicidad,
               genesis_session_id, coalesce((plan_anual->>'aprobado')::boolean, false) as aprobado
        from annual_plans order by user_id, created_at desc""")}
    genesis = {r["genesis_session_id"] for r in plan.values() if r["genesis_session_id"]}
    sesiones: dict[str, list] = {}
    for r in await _filas(db, "select id, user_id, created_at from board_sessions"):
        if r["id"] not in genesis:  # la sesión génesis la crea el sistema al generar el plan
            sesiones.setdefault(r["user_id"], []).append(r["created_at"])
    tareas = {r["user_id"]: r for r in await _filas(db, """
        select p.user_id, count(t.id) as total,
               count(t.id) filter (where t.status = 'completada') as completadas
        from annual_plans p
        join monthly_plans m on m.annual_plan_id = p.id
        join objectives o on o.monthly_plan_id = m.id
        join action_tasks t on t.objective_id = o.id
        where p.status = 'active' and t.incluida
        group by p.user_id""")}
    docs = {r["user_id"]: r["n"] for r in await _filas(db, """
        select user_id, count(*) as n from documents group by user_id""")}

    out = []
    for u in users:
        uid = u["id"]
        o, p, d, t = onb.get(uid) or {}, plan.get(uid) or {}, diag.get(uid) or {}, tareas.get(uid) or {}
        ses = sorted(sesiones.get(uid, []))
        onboarding_ok = 8 in (o.get("completed_stages") or [])
        if ses:
            etapa = "sesionando"
        elif p.get("aprobado"):
            etapa = "plan_aprobado"
        elif p.get("roadmap_status") == "validado":
            etapa = "estrategia_validada"
        elif p.get("status") in ("active", "generating"):
            etapa = "estrategia"
        elif onboarding_ok or d:
            etapa = "diagnostico"
        elif uid in todd or o:
            etapa = "onboarding"
        else:
            etapa = "registrado"
        out.append({
            "id": uid,
            "email": u["email"],
            "registrado": u["created_at"],
            "ultimo_acceso": u["last_sign_in_at"],
            "empresa": o.get("empresa"),
            "industria": o.get("industria"),
            "etapa": etapa,
            "plan_estado": p.get("status"),
            "periodicidad": p.get("periodicidad"),
            "sesiones": len(ses),
            "ultima_sesion": ses[-1] if ses else None,
            "tareas_total": int(t.get("total") or 0),
            "tareas_completadas": int(t.get("completadas") or 0),
            "documentos": int(docs.get(uid) or 0),
        })
    return out


@router.get("/admin/resumen")
async def admin_resumen(_: dict = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    usuarios = await _usuarios(db)
    ahora = datetime.now(timezone.utc)

    def desde(campo: str, dias: int) -> int:
        lim = ahora - timedelta(days=dias)
        return sum(1 for u in usuarios if u[campo] and u[campo] >= lim)

    orden = [k for k, _ in ETAPAS]
    # Embudo acumulado: cuántos llegaron AL MENOS a cada etapa.
    embudo = [
        {"etapa": k, "label": label,
         "usuarios": sum(1 for u in usuarios if orden.index(u["etapa"]) >= i)}
        for i, (k, label) in enumerate(ETAPAS)
    ]
    total_sesiones = sum(u["sesiones"] for u in usuarios)
    return {
        "usuarios_total": len(usuarios),
        "nuevos_7d": desde("registrado", 7),
        "nuevos_30d": desde("registrado", 30),
        "activos_7d": desde("ultimo_acceso", 7),
        "activos_30d": desde("ultimo_acceso", 30),
        "sesiones_total": total_sesiones,
        "con_plan": sum(1 for u in usuarios if u["plan_estado"] == "active"),
        "embudo": embudo,
        "etapas": [{"etapa": k, "label": label} for k, label in ETAPAS],
        "usuarios": usuarios,
        # Sin pasarela de pago todavía: el frontend lo muestra como "próximamente".
        "cobros_activos": False,
    }
