"""Biblioteca de Gobernia: los documentos VALIDADOS del cliente, listos para el consejo.
v1: el Roadmap estratégico validado — TODAS sus versiones, la más reciente primero.
Cada versión es un snapshot inmutable, en solo lectura. (Se le sumarán más tipos de documento.)
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_db
from app.models.annual_plan import AnnualPlan
from app.models.roadmap_version import RoadmapVersion

router = APIRouter()

_DESCRIPCION = "Documento ejecutivo del plan a 3 años, validado por el dueño."
_ESTADO = "pendiente de revisar en consejo"


@router.get("/biblioteca")
async def get_biblioteca(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    versiones = (await db.execute(
        select(RoadmapVersion)
        .where(RoadmapVersion.user_id == user_id)
        .order_by(RoadmapVersion.version.desc())
    )).scalars().all()

    if versiones:
        return {"items": [
            {
                "tipo": "roadmap",
                "titulo": f"Roadmap Estratégico — v{v.version}",
                "descripcion": _DESCRIPCION,
                "validado_at": v.validated_at,
                "version": v.version,
                "estado": _ESTADO,
                "pdf_path": f"/annual-plan/roadmap/versiones/{v.id}/pdf",
            }
            for v in versiones
        ]}

    # Retrocompatibilidad: planes validados ANTES de que existiera el versionado
    # no tienen snapshot archivado; se sigue mostrando el roadmap actual.
    plan = (await db.execute(
        select(AnnualPlan).where(AnnualPlan.user_id == user_id)
        .order_by(AnnualPlan.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    items = []
    if plan is not None and plan.roadmap and plan.roadmap_status == "validado":
        items.append({
            "tipo": "roadmap",
            "titulo": "Roadmap estratégico",
            "descripcion": _DESCRIPCION,
            "validado_at": plan.roadmap_validated_at,
            "version": 1,
            "estado": _ESTADO,
            "pdf_path": "/annual-plan/roadmap/pdf",
        })
    return {"items": items}
