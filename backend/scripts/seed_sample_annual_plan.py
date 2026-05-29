"""
Siembra un AnnualPlan de muestra (status 'active') para probar el frontend localmente,
SIN IA ni Celery. Inserta 12 meses; los primeros con objetivos y tareas de ejemplo.

USO (desde backend/):
    venv/bin/python -m scripts.seed_sample_annual_plan <USER_ID> [--status active|generating]

Si no se pasa USER_ID, usa el del usuario de prueba (variable SEED_USER_ID o un default).
"""
import asyncio
import sys
from datetime import date

from sqlalchemy import delete, select
from app.db.session import AsyncSessionLocal
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.action_plan import ActionTask
from app.services.ai.annual_plan_generator import month_calendar, compute_active_month_index

DEFAULT_USER_ID = "seed-user"

SAMPLE = {
    1: {"focus": "Estabilizar liquidez", "objectives": [
        {"title": "Mejorar el flujo de caja", "kpi_refs": ["Razón corriente"], "tasks": [
            {"title": "Negociar línea de crédito revolvente", "owner": "CFO", "priority": "alta"},
            {"title": "Revisar política de cuentas por cobrar", "owner": "Director General", "priority": "media"},
        ]},
        {"title": "Ordenar el gobierno corporativo", "kpi_refs": ["Governance Score"], "tasks": [
            {"title": "Documentar el reglamento del consejo", "owner": "Auditor Interno", "priority": "media"},
        ]},
    ]},
    2: {"focus": "Impulsar ventas", "objectives": [
        {"title": "Diversificar la cartera de clientes", "kpi_refs": ["Concentración de clientes"], "tasks": [
            {"title": "Definir plan comercial por segmento", "owner": "Director Comercial", "priority": "alta"},
        ]},
    ]},
    3: {"focus": "Fortalecer talento", "objectives": [
        {"title": "Reducir rotación clave", "kpi_refs": ["Rotación de personal"], "tasks": [
            {"title": "Diseñar plan de retención de directivos", "owner": "Director de RH", "priority": "media"},
        ]},
    ]},
}


async def main(user_id: str, status: str) -> None:
    today = date.today()
    async with AsyncSessionLocal() as db:
        # Limpiar planes previos del usuario (idempotente para re-sembrar).
        prev = await db.execute(select(AnnualPlan).where(AnnualPlan.user_id == user_id))
        for p in prev.scalars().all():
            await db.execute(delete(AnnualPlan).where(AnnualPlan.id == p.id))
        await db.commit()

        plan = AnnualPlan(
            user_id=user_id,
            title="Plan estratégico de 12 meses",
            start_date=today,
            status=status,
            diagnostico_summary=(
                "**CFO:** La liquidez está ajustada; conviene asegurar una línea de crédito.\n\n"
                "**CSO:** Las ventas dependen de pocos clientes; urge diversificar.\n\n"
                "**CRO:** El principal riesgo es de concentración comercial.\n\n"
                "**Auditor:** El gobierno corporativo necesita formalizar su reglamento."
            ),
        )
        db.add(plan)
        await db.flush()

        active_idx = compute_active_month_index(today, today)  # = 1
        for i in range(1, 13):
            year, month = month_calendar(today.year, today.month, i)
            mp = MonthlyPlan(
                annual_plan_id=plan.id, month_index=i,
                period_year=year, period_month=month,
                focus=SAMPLE.get(i, {}).get("focus"),
                status="active" if i == active_idx else ("done" if i < active_idx else "locked"),
            )
            db.add(mp)
            await db.flush()

            for oi, obj_spec in enumerate(SAMPLE.get(i, {}).get("objectives", [])):
                obj = Objective(
                    monthly_plan_id=mp.id, title=obj_spec["title"],
                    kpi_refs=obj_spec.get("kpi_refs", []), order_index=oi,
                )
                db.add(obj)
                await db.flush()
                for ti, t in enumerate(obj_spec.get("tasks", [])):
                    db.add(ActionTask(
                        objective_id=obj.id, title=t["title"],
                        status="pendiente", priority=t.get("priority", "media"),
                        owner=t.get("owner"),
                        due_date=date(year, month, 25),
                        kpi_ref=(obj_spec.get("kpi_refs") or [None])[0],
                        tags=[], order_index=ti,
                    ))
        await db.commit()
    print(f"OK: plan de muestra sembrado para user_id={user_id} (status={status})")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    uid = args[0] if args else DEFAULT_USER_ID
    st = "active"
    if "--status" in sys.argv:
        st = sys.argv[sys.argv.index("--status") + 1]
    asyncio.run(main(uid, st))
