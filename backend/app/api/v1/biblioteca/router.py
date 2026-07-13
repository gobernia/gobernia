"""Biblioteca de Gobernia: los documentos VALIDADOS del cliente, listos para el consejo.
v1: el Roadmap estratégico validado. (Se le sumarán más tipos de documento después.)
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_db
from app.models.annual_plan import AnnualPlan

router = APIRouter()


@router.get("/biblioteca")
async def get_biblioteca(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    plan = (await db.execute(
        select(AnnualPlan).where(AnnualPlan.user_id == user_id)
        .order_by(AnnualPlan.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    items = []
    if plan is not None and plan.roadmap and plan.roadmap_status == "validado":
        items.append({
            "tipo": "roadmap",
            "titulo": "Roadmap estratégico",
            "descripcion": "Documento ejecutivo del plan a 3 años, validado por el dueño.",
            "validado_at": plan.roadmap_validated_at,
            "estado": "pendiente de revisar en consejo",
            "pdf_path": "/annual-plan/roadmap/pdf",
        })
    return {"items": items}
