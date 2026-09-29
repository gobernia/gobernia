"""Arma el `contexto` del tablero para Todd secretario (tablero + roadmap + acuerdos).

Todd NO consulta la BD: esta capa le entrega el estado ya resumido y eficiente
(selectinload + una sola consulta de tareas, sin N+1).
"""
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.board_session import BoardSession
from app.models.compromiso import Compromiso
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.onboarding_session import OnboardingSession
from app.schemas.etapa7 import DOCUMENT_TYPE_LABELS
from app.services.evidencia_revision import validacion_visible

# Discriminador para reusar ChatMessage sin columnas nuevas.
TODD_SECRETARIO_AGENT = "todd_secretario"

# Tope de tareas que se listan en el prompt (el prompt no debe crecer sin límite).
_MAX_TAREAS = 40
# Tope de documentos en el inventario de Todd (los más recientes).
_MAX_DOCUMENTOS = 60
_ESTADOS = ("pendiente", "en_progreso", "completada")


async def get_anchor_board_session_id(
    user_id: str, db: AsyncSession
) -> uuid.UUID | None:
    """El chat de Todd secretario es del usuario, pero ChatMessage exige un board_session_id.
    Lo anclamos a la sesión de consejo más reciente del usuario (si tiene alguna)."""
    row = await db.execute(
        select(BoardSession.id)
        .where(BoardSession.user_id == user_id)
        .order_by(BoardSession.created_at.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


async def _empresa_nombre(user_id: str, db: AsyncSession) -> str:
    onb = (await db.execute(
        select(OnboardingSession)
        .where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    c = (((onb.memory_buffer if onb else {}) or {}).get("company") or {})
    partes = [str(c[k]) for k in ("name", "industry") if c.get(k)]
    return " · ".join(partes)


def _tarea_dict(t: ActionTask) -> dict:
    return {
        "task_id": str(t.id),
        "title": t.title,
        "status": t.status,
        "owner": t.owner or "",
        "priority": t.priority,
        "due_date": t.due_date.isoformat() if t.due_date else None,
    }


async def build_contexto(user_id: str, db: AsyncSession) -> dict:
    """Contexto completo para Todd: tablero (por estado + atrasadas + responsables),
    roadmap resumido (visión + pilares) y acuerdos abiertos."""
    empresa = await _empresa_nombre(user_id, db)

    # Plan anual activo (con sus meses y objetivos precargados) — es el tablero.
    plan = (await db.execute(
        select(AnnualPlan)
        .where(AnnualPlan.user_id == user_id, AnnualPlan.status == "active")
        .order_by(AnnualPlan.created_at.desc())
        .options(selectinload(AnnualPlan.months).selectinload(MonthlyPlan.objectives))
        .limit(1)
    )).scalars().first()

    tareas: list[ActionTask] = []
    roadmap_resumen: dict = {}
    if plan is not None:
        objetivo_ids = [
            obj.id
            for mes in (plan.months or [])
            for obj in (mes.objectives or [])
        ]
        if objetivo_ids:
            tareas = list((await db.execute(
                select(ActionTask)
                .where(ActionTask.objective_id.in_(objetivo_ids))
                .order_by(ActionTask.due_date.is_(None), ActionTask.due_date, ActionTask.order_index)
            )).scalars().all())

        rm = plan.roadmap or {}
        roadmap_resumen = {
            "vision": str(rm.get("vision") or "").strip(),
            "pilares": [
                {
                    "nombre": str(p.get("nombre") or "").strip(),
                    "objetivo": str(p.get("objetivo") or p.get("descripcion") or "").strip(),
                }
                for p in (rm.get("pilares") or [])
                if isinstance(p, dict) and str(p.get("nombre") or "").strip()
            ],
        }

    hoy = date.today()
    por_estado = {e: 0 for e in _ESTADOS}
    responsables: dict[str, int] = {}
    atrasadas: list[dict] = []
    for t in tareas:
        por_estado[t.status] = por_estado.get(t.status, 0) + 1
        if t.owner:
            responsables[t.owner] = responsables.get(t.owner, 0) + 1
        if t.due_date and t.due_date < hoy and t.status != "completada":
            atrasadas.append(_tarea_dict(t))

    tablero = {
        "total": len(tareas),
        "por_estado": por_estado,
        "responsables": responsables,
        "atrasadas": atrasadas,
        "tareas": [_tarea_dict(t) for t in tareas[:_MAX_TAREAS]],
    }

    # Acuerdos abiertos del Consejo.
    acuerdos_rows = (await db.execute(
        select(Compromiso)
        .where(Compromiso.user_id == user_id, Compromiso.status == "abierto")
        .order_by(Compromiso.created_at)
    )).scalars().all()
    acuerdos = [
        {
            "descripcion": c.descripcion,
            "responsable": c.responsable_nombre or "",
            "prioridad": c.prioridad,
            "pilar": c.pilar or "",
        }
        for c in acuerdos_rows
    ]

    documentos, abrir = await documentos_del_usuario(user_id, db, tareas)

    return {
        "empresa": empresa,
        "tablero": tablero,
        "roadmap": roadmap_resumen,
        "acuerdos_abiertos": acuerdos,
        "documentos": documentos,
        # Solo para el router (abrir un documento por su ref); no se renderiza en el prompt.
        "_documentos_abrir": abrir,
    }


async def documentos_del_usuario(
    user_id: str, db: AsyncSession, tareas: list[ActionTask] | None = None,
) -> tuple[list[dict], dict[str, dict]]:
    """Inventario de TODOS los documentos de la empresa para Todd: evidencias de los puntos del
    tablero, repositorio de "Mis consejeros" y documentos de sesiones del Consejo.

    Devuelve (inventario para el prompt, {ref: {s3_key, filename}} para abrirlos). El `ref`
    (E1, D1…) es lo único que Todd ve; la llave de almacenamiento nunca llega al modelo.
    """
    if tareas is None:
        tareas = []
    por_tarea = {t.id: t for t in tareas}
    items: list[tuple] = []  # (fecha, prefijo, dict_visible, s3_key)

    if por_tarea:
        evs = (await db.execute(
            select(Evidence).where(Evidence.action_task_id.in_(list(por_tarea)))
        )).scalars().all()
        for e in evs:
            t = por_tarea[e.action_task_id]
            v = validacion_visible(t.validacion) or {}
            items.append((e.created_at, "E", {
                "nombre": e.filename,
                "origen": f"evidencia del punto «{t.title}»" + (f" (responsable: {t.owner})" if t.owner else ""),
                "veredicto": v.get("estado"),
                "motivo": v.get("motivo") or "",
            }, e.s3_key))

    docs = (await db.execute(select(Document).where(Document.user_id == user_id))).scalars().all()
    for d in docs:
        tipo = DOCUMENT_TYPE_LABELS.get(d.document_type, d.document_type)
        origen = ("documento de una sesión del Consejo" if d.board_session_id
                  else "repositorio de la empresa (Mis consejeros)")
        items.append((d.created_at, "D", {"nombre": d.filename, "origen": f"{origen} · {tipo}"}, d.s3_key))

    items.sort(key=lambda x: x[0], reverse=True)
    inventario: list[dict] = []
    abrir: dict[str, dict] = {}
    cuenta = {"E": 0, "D": 0}
    for fecha, pref, vis, key in items[:_MAX_DOCUMENTOS]:
        cuenta[pref] += 1
        ref = f"{pref}{cuenta[pref]}"
        inventario.append({"ref": ref, "fecha": fecha.date().isoformat() if fecha else None, **vis})
        abrir[ref] = {"s3_key": key, "filename": vis["nombre"]}
    return inventario, abrir
