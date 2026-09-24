"""Completa el detalle (fases, milestones, estrategias…) de los pilares que quedaron vacíos
en roadmaps ya guardados. Conserva el NOMBRE y el ORDEN de cada pilar, para no desenlazar
los objetivos y puntos de agenda que ya cuelgan de ellos, y nunca pisa lo que ya existe.

TOCA LA BASE DE PRODUCCIÓN — solo con autorización humana.

Uso:
  python scripts/completar_roadmap_pilares.py correo@x.com            # simulación (no guarda)
  python scripts/completar_roadmap_pilares.py correo@x.com --aplicar  # guarda
  python scripts/completar_roadmap_pilares.py correo@x.com --generar  # simula un roadmap NUEVO completo
"""
import asyncio
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.models.annual_plan import AnnualPlan  # noqa: E402
from app.models.board_session import BoardSession  # noqa: E402
from app.models.diagnostico_estrategico import DiagnosticoEstrategico  # noqa: E402
from app.models.onboarding_session import OnboardingSession  # noqa: E402
from app.services.ai.foda_into_plan import augment_buffer_with_foda  # noqa: E402
from app.services.ai.roadmap import (  # noqa: E402
    _contexto, completar_pilares, generate_roadmap, pilar_completo,
)


async def main(email: str, aplicar: bool, generar: bool) -> None:
    async with AsyncSessionLocal() as db:
        uid = (await db.execute(text("select id::text from auth.users where email=:e"), {"e": email})).scalar()
        if uid is None:
            sys.exit(f"No existe {email}")
        plan = (await db.execute(
            select(AnnualPlan).where(AnnualPlan.user_id == uid, AnnualPlan.roadmap.isnot(None))
            .order_by(AnnualPlan.created_at.desc()))).scalars().first()
        if plan is None:
            sys.exit("Sin roadmap")

        onb = (await db.execute(select(OnboardingSession).where(OnboardingSession.user_id == uid)
                                .order_by(OnboardingSession.created_at.desc()))).scalars().first()
        diag = (await db.execute(select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == uid)
                                 .order_by(DiagnosticoEstrategico.created_at.desc()))).scalars().first()
        dcont = (diag.content if diag else {}) or {}
        mb = augment_buffer_with_foda((onb.memory_buffer if onb else {}) or {}, dcont.get("foda"),
                                      dcont.get("metas_orden") or [], perspectivas=dcont.get("perspectivas"))
        genesis = await db.get(BoardSession, plan.genesis_session_id) if plan.genesis_session_id else None
        postura = genesis.conclusion if genesis and (genesis.conclusion or {}).get("conclusion") else None

        if generar:
            rm = await asyncio.to_thread(generate_roadmap, mb, dcont, postura)
            _resumen(rm)
            return

        rm = copy.deepcopy(plan.roadmap)
        antes = [p["nombre"] for p in rm.get("pilares") or []]
        system, contexto = _contexto(mb, dcont, postura)
        await asyncio.to_thread(completar_pilares, rm, system, contexto)
        assert [p["nombre"] for p in rm["pilares"]] == antes, "cambió nombre/orden de pilares"
        _resumen(rm)

        if aplicar:
            respaldo = Path(__file__).parent / f"respaldo_roadmap_{plan.id}.json"
            respaldo.write_text(json.dumps(plan.roadmap, ensure_ascii=False, indent=1))
            plan.roadmap = rm
            flag_modified(plan, "roadmap")
            await db.commit()
            print(f"GUARDADO. Respaldo del original: {respaldo}")
        else:
            print("Simulación: no se guardó nada (usa --aplicar).")
    await engine.dispose()


def _resumen(rm: dict) -> None:
    for i, p in enumerate(rm.get("pilares") or [], 1):
        mi = p.get("milestones") or {}
        print(f"{i}. {p['nombre'][:70]}")
        print(f"   completo={pilar_completo(p)} estrategias={len(p.get('estrategias') or [])} "
              f"kpis={len(p.get('kpis') or [])} temas_consejo={len(p.get('temas_consejo') or [])} "
              f"milestones={[len(mi.get(a) or []) for a in ('anio1', 'anio2', 'anio3')]}")
        print(f"   fases={[f.get('titulo') for f in (p.get('fases') or {}).values()]}")
        print(f"   ej. año 1: {(mi.get('anio1') or ['—'])[0][:110]}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    asyncio.run(main(args[0], "--aplicar" in sys.argv, "--generar" in sys.argv))
