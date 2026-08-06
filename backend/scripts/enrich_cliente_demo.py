"""Enriquece una cuenta de demo YA sembrada con lo NUEVO de la cadena estratégica.

Sobre lo que deja `seed_demo_completo.py`, añade:
  1. razón + riesgos por prioridad en el roadmap.
  2. Plan anual APROBADO (4 prioridades) → activa la orden del día conectada.
  3. pilar_index en cada objetivo (vínculo tarea→prioridad) → análisis por punto.
  4. required_doc en las tareas → documentos solicitados por punto.
  5. Unos acuerdos (Compromiso) ligados a su prioridad → acuerdos por punto.

Idempotente. Uso: PYTHONPATH=. venv/bin/python scripts/enrich_cliente_demo.py <email>
"""
import asyncio
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.db.session import AsyncSessionLocal
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.action_plan import ActionTask
from app.models.compromiso import Compromiso
from app.services.governance.pilar_link import infer_pilar_index

# razón + riesgos por prioridad (keyed por nombre del pilar del roadmap del seed).
ENRIQUECIMIENTO = {
    "Rentabilidad y control": {
        "razon": "Sin ver la rentabilidad real por proyecto, la empresa decide a ciegas y sangra margen.",
        "riesgos": [
            "El cierre contable lento oculta las pérdidas hasta que ya es tarde.",
            "Descuentos sin piso de margen erosionan la utilidad proyecto a proyecto.",
        ],
    },
    "Diversificación comercial": {
        "razon": "El 58% de los ingresos está en 3 cuentas: perder una amenaza la continuidad del negocio.",
        "riesgos": [
            "Alta dependencia de 3 clientes clave.",
            "Pipeline comercial insuficiente para reemplazar una cuenta grande.",
        ],
    },
    "Talento y cultura": {
        "razon": "Con 31% de rotación se va el conocimiento y sube el costo de operar.",
        "riesgos": [
            "Fuga de talento clave sin un plan de retención.",
            "Falta de un segundo mando que sostenga la operación.",
        ],
    },
    "Gobierno y sucesión": {
        "razon": "La dirección es el cuello de botella de toda decisión; sin gobierno no hay escala ni continuidad.",
        "riesgos": [
            "Concentración de decisiones críticas en el dueño.",
            "Ausencia de un plan de sucesión formal.",
        ],
    },
    "Innovación y eficiencia": {
        "razon": "Diferenciarse por producto y eficiencia es lo que sostiene el margen frente a la competencia.",
        "riesgos": [
            "Procesos manuales que no escalan con el crecimiento.",
            "Rezago frente a competidores más digitales.",
        ],
    },
}

# Documento a solicitar por prioridad (índice del pilar → doc).
DOC_POR_PILAR = {
    0: "Estado de resultados del mes, por proyecto",
    1: "Reporte de ventas por cliente del periodo",
    2: "Reporte de rotación y organigrama actualizado",
    3: "Acta de la última sesión de gobierno",
    4: "Reporte de avance de iniciativas de eficiencia",
}


async def enrich(email: str) -> None:
    hoy = date.today()
    async with AsyncSessionLocal() as db:
        row = await db.execute(text("SELECT id FROM auth.users WHERE email = :e"), {"e": email})
        u = row.fetchone()
        if not u:
            print(f"❌ No existe {email!r} en auth.users. Corre create_auth_user + seed primero.")
            return
        user_id = str(u[0])

        res = await db.execute(
            select(AnnualPlan).where(AnnualPlan.user_id == user_id, AnnualPlan.status == "active")
            .order_by(AnnualPlan.created_at.desc()).limit(1)
        )
        plan = res.scalar_one_or_none()
        if plan is None or not (plan.roadmap or {}).get("pilares"):
            print("❌ No hay AnnualPlan activo con roadmap. Corre el seed primero.")
            return

        pilares = plan.roadmap["pilares"]

        # 1) razón + riesgos por prioridad
        for p in pilares:
            extra = ENRIQUECIMIENTO.get(p.get("nombre"))
            if extra:
                p["razon"] = extra["razon"]
                p["riesgos"] = extra["riesgos"]
        flag_modified(plan, "roadmap")

        # 2) Plan anual aprobado (las primeras 4 prioridades)
        elegidos = list(range(min(4, len(pilares))))
        snapshot = [{
            "indice": i,
            "nombre": pilares[i].get("nombre"),
            "descripcion": pilares[i].get("descripcion"),
            "razon": pilares[i].get("razon"),
            "objetivo": pilares[i].get("objetivo"),
            "kpis": list(pilares[i].get("kpis") or []),
            "estrategias": list(pilares[i].get("estrategias") or []),
            "riesgos": list(pilares[i].get("riesgos") or []),
        } for i in elegidos]
        plan.plan_anual = {
            "anio": hoy.year,
            "aprobado": True,
            "aprobado_at": datetime.now(timezone.utc).isoformat(),
            "pilares": snapshot,
        }
        flag_modified(plan, "plan_anual")

        # 3 y 4) pilar_index en objetivos + required_doc en tareas
        mres = await db.execute(
            select(MonthlyPlan).where(MonthlyPlan.annual_plan_id == plan.id)
            .options(selectinload(MonthlyPlan.objectives))
        )
        months = mres.scalars().all()
        obj_ids = [o.id for m in months for o in m.objectives]
        tres = await db.execute(select(ActionTask).where(ActionTask.objective_id.in_(obj_ids))) if obj_ids else None
        tasks = list(tres.scalars().all()) if tres else []
        tasks_por_obj: dict[uuid.UUID, list[ActionTask]] = {}
        for t in tasks:
            tasks_por_obj.setdefault(t.objective_id, []).append(t)

        n_obj_ligados = 0
        n_docs = 0
        for m in months:
            for o in m.objectives:
                idx = infer_pilar_index(o.kpi_refs, f"{o.title} {o.description or ''}", pilares)
                o.pilar_index = idx
                if idx is not None:
                    n_obj_ligados += 1
                    doc = DOC_POR_PILAR.get(idx)
                    for t in tasks_por_obj.get(o.id, []):
                        if doc and not (t.required_doc or "").strip():
                            t.required_doc = doc
                            n_docs += 1

        # 5) Acuerdos ligados a su prioridad (para el bloque de acuerdos por punto)
        acuerdos_seed = [
            (0, "Aprobar la política de precios con piso de margen por tipo de proyecto.", "Dirección de Finanzas", 20, "alta"),
            (1, "Presentar el plan de prospección para reducir la dependencia de las 3 cuentas.", "Dirección Comercial", 30, "alta"),
            (2, "Definir el plan de retención del talento clave y del segundo mando.", "Dirección de Personas", 45, "media"),
        ]
        # Idempotencia: no dupliques si ya se corrió antes.
        ya = await db.execute(select(Compromiso).where(Compromiso.user_id == user_id))
        existentes = {c.descripcion for c in ya.scalars().all()}
        n_acuerdos = 0
        for idx, desc, resp, dias, prio in acuerdos_seed:
            if desc in existentes or idx >= len(pilares):
                continue
            db.add(Compromiso(
                user_id=user_id, descripcion=desc, responsable_nombre=resp,
                fecha_compromiso=hoy + timedelta(days=dias), status="abierto",
                token=uuid.uuid4().hex, prioridad=prio, pilar=pilares[idx].get("nombre"),
            ))
            n_acuerdos += 1

        await db.commit()
        print("✅ Enriquecido:", email)
        print(f"   • razón + riesgos en {sum(1 for p in pilares if p.get('razon'))} prioridades")
        print(f"   • Plan anual APROBADO con {len(snapshot)} prioridades")
        print(f"   • {n_obj_ligados} objetivos ligados a su prioridad (pilar_index)")
        print(f"   • {n_docs} tareas con documento solicitado")
        print(f"   • {n_acuerdos} acuerdos sembrados")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: enrich_cliente_demo.py <email>")
        raise SystemExit(1)
    asyncio.run(enrich(sys.argv[1]))
