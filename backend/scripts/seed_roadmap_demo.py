"""Siembra un AnnualPlan 'active' con un ROADMAP de ejemplo para un usuario (por correo),
para poder ver la vista Roadmap (timeline pilares×años) sin rehacer todo el flujo.
Idempotente: borra el plan anual previo del usuario (cascade limpia meses/objetivos/tareas).

USO (desde backend/, solo con autorización — toca la DB):
    venv/bin/python -m scripts.seed_roadmap_demo correo@ejemplo.com
"""
import asyncio
import sys
from datetime import date

from sqlalchemy import delete, text

from app.db.session import AsyncSessionLocal
from app.models.annual_plan import AnnualPlan

ROADMAP = {
    "vision": "Ser el referente en México en desarrollo de apps y plataformas digitales robustas, "
              "duplicando ingresos en 3 años con rentabilidad sana y clientes diversificados.",
    "mision": "Construir software que impulse el crecimiento de nuestros clientes, con excelencia "
              "técnica y cercanía.",
    "propuesta_valor": "Plataformas a la medida, confiables y de rápido time-to-market, con "
                       "acompañamiento estratégico, no solo desarrollo.",
    "metas_3anios": [
        {"meta": "Duplicar los ingresos anuales", "kpi": "Crecimiento de ventas", "valor_actual": "4%", "target": "15%"},
        {"meta": "Mejorar la rentabilidad", "kpi": "Margen neto", "valor_actual": "6%", "target": "12%"},
        {"meta": "Diversificar la cartera de clientes", "kpi": "Concentración top-3", "valor_actual": "55%", "target": "30%"},
        {"meta": "Reducir la rotación de personal", "kpi": "Rotación", "valor_actual": "22%", "target": ""},
    ],
    "resumen_foda": "Fortaleza técnica y buena calidad, pero márgenes apretados y alta dependencia de "
                    "pocos clientes. La oportunidad de mercado es amplia; la amenaza principal es la "
                    "competencia de bajo costo.",
    "resumen_entorno": "Mercado digital en crecimiento y demanda sostenida de plataformas a la medida; "
                       "presión de precios por competidores regionales y talento técnico escaso.",
    "pilares": [
        {"nombre": "Excelencia operacional",
         "descripcion": "Procesos claros y previsibles que protejan el margen.",
         "milestones": {
             "anio1": ["Mapear e instrumentar los procesos clave", "Implementar tablero de indicadores"],
             "anio2": ["Certificar procesos (ISO)", "Automatizar 40% de la operación"],
             "anio3": ["Automatizar 60% de la operación", "Costeo por proyecto en tiempo real"]}},
        {"nombre": "Expansión de mercado",
         "descripcion": "Diversificar clientes y reducir la concentración.",
         "milestones": {
             "anio1": ["Programa de prospección activa", "Cerrar 3 clientes fuera del top-3"],
             "anio2": ["Abrir un nuevo segmento de industria", "Concentración top-3 < 45%"],
             "anio3": ["Presencia en 2 regiones nuevas", "Concentración top-3 < 30%"]}},
        {"nombre": "Talento y cultura",
         "descripcion": "Retener y desarrollar al equipo clave.",
         "milestones": {
             "anio1": ["Plan de carrera y compensación por desempeño", "Reducir rotación a 18%"],
             "anio2": ["Programa de capacitación (DNC)", "Reducir rotación a 14%"],
             "anio3": ["Liderazgo técnico consolidado", "Rotación en el promedio de la industria"]}},
        {"nombre": "Gobierno corporativo",
         "descripcion": "Profesionalizar la toma de decisiones.",
         "milestones": {
             "anio1": ["Instalar consejo consultivo", "Sesiones trimestrales con indicadores"],
             "anio2": ["Planeación estratégica formal anual", "Crear reserva de capital"],
             "anio3": ["Gobierno maduro y sucesión clara", "Ser sujeto de crédito"]}},
    ],
}


async def main(email: str) -> None:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(text("SELECT id FROM auth.users WHERE email = :e"), {"e": email})).first()
        if not row:
            print(f"❌ No existe usuario con el correo {email!r}.")
            return
        user_id = str(row[0])
        await db.execute(delete(AnnualPlan).where(AnnualPlan.user_id == user_id))
        plan = AnnualPlan(
            user_id=user_id, title="Plan estratégico de 3 año(s)", start_date=date.today(),
            status="active", horizon_years=3, roadmap=ROADMAP,
        )
        db.add(plan)
        await db.commit()
        print(f"✅ Roadmap de ejemplo sembrado para {email}. Entra a Plan → Roadmap.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: venv/bin/python -m scripts.seed_roadmap_demo correo@ejemplo.com")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
