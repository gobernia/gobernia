"""Backfill de objectives.pilar_index para planes ya existentes.

Para cada AnnualPlan con roadmap["pilares"], recorre todos los objetivos de sus
MonthlyPlans y (re)calcula pilar_index con infer_pilar_index. Idempotente:
recalcula y sobreescribe. Al final imprime cuántos objetivos quedaron con pilar
asignado y cuántos en None.

USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.backfill_objective_pilar

OJO: usa el DATABASE_URL configurado (apunta a PROD). Correr SOLO con autorización.
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.services.governance.pilar_link import infer_pilar_index


async def main() -> None:
    total_objs = 0
    con_pilar = 0
    en_none = 0
    planes_procesados = 0

    async with AsyncSessionLocal() as db:
        plans = (await db.execute(
            select(AnnualPlan).options(
                selectinload(AnnualPlan.months).selectinload(MonthlyPlan.objectives)
            )
        )).scalars().all()

        for plan in plans:
            roadmap = plan.roadmap if isinstance(plan.roadmap, dict) else None
            pilares = (roadmap or {}).get("pilares")
            if not pilares:
                continue
            planes_procesados += 1

            for month in plan.months:
                for obj in month.objectives:
                    total_objs += 1
                    idx = infer_pilar_index(
                        obj.kpi_refs,
                        f"{obj.title} {obj.description or ''}",
                        pilares,
                    )
                    obj.pilar_index = idx
                    if idx is None:
                        en_none += 1
                    else:
                        con_pilar += 1

        await db.commit()

    print(f"Planes con roadmap procesados: {planes_procesados}")
    print(f"Objetivos revisados:           {total_objs}")
    print(f"  - con pilar asignado:        {con_pilar}")
    print(f"  - en None (sin match):       {en_none}")


if __name__ == "__main__":
    asyncio.run(main())
