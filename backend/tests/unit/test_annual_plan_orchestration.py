import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.tasks.annual_plan_tasks as orch


def test_kpi_labels_from_buffer():
    buf = {"kpis": {"finanzas": [{"label": "Razón corriente"}, {"label": "EBITDA"}],
                    "comercial": [{"label": "CAC"}]}}
    labels = orch.kpi_labels_from_buffer(buf)
    assert set(labels) == {"Razón corriente", "EBITDA", "CAC"}
    assert orch.kpi_labels_from_buffer({}) == []


@pytest.mark.asyncio
async def test_run_generation_happy_path(monkeypatch):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.start_date = date(2026, 5, 1)
    plan.status = "generating"

    onboarding = MagicMock()
    onboarding.memory_buffer = {"company": {"name": "Demo"}, "kpis": {}}

    db = AsyncMock()
    db.get = AsyncMock(return_value=plan)
    result = MagicMock()
    result.scalar_one_or_none.return_value = onboarding
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.add_all = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    plan.horizon_years = 1

    monkeypatch.setattr(orch, "run_diagnostico", lambda buf: ({"CFO": {"summary": "ok"}}, {"CFO": {}}))
    monkeypatch.setattr(orch, "synthesize_diagnostico", lambda a: "Diag")
    monkeypatch.setattr(orch, "generate_milestones",
                        lambda *a, **k: {"items": []})
    monkeypatch.setattr(orch, "generate_quarter_plan",
                        lambda memory_buffer, kpi_labels, milestones, y, q: [
                            {"month_index": (y - 1) * 12 + (q - 1) * 3 + i,
                             "focus": "f", "objectives": []}
                            for i in range(1, 4)])

    await orch._run_generation(str(plan.id), db)

    assert plan.status == "active"
    assert plan.diagnostico_summary == "Diag"
    assert db.add_all.called or db.add.called
    assert db.commit.await_count >= 1

    # Idempotencia: se emitió un DELETE sobre monthly_plans antes de poblar.
    from sqlalchemy.sql.dml import Delete
    assert any(c.args and isinstance(c.args[0], Delete) for c in db.execute.call_args_list)


@pytest.mark.asyncio
async def test_run_generation_marks_failed_on_error(monkeypatch):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.start_date = date(2026, 5, 1)
    plan.status = "generating"

    db = AsyncMock()
    db.get = AsyncMock(return_value=plan)
    db.commit = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        await orch._run_generation(str(plan.id), db)
    assert plan.status == "failed"


def test_run_diagnostico_applies_challenger(monkeypatch):
    from app.services.ai.agents import base

    monkeypatch.setattr(base, "run_agent_analysis",
                        lambda agent, *a, **k: {"summary": f"{agent} initial"})
    monkeypatch.setattr(base, "run_challenger_critique",
                        lambda *a, **k: {"weak_assumptions": ["supuesto débil"]})
    monkeypatch.setattr(base, "run_agent_revision",
                        lambda agent, initial, critique, *a, **k: {"summary": f"{agent} revised"})

    analyses, critiques = orch.run_diagnostico({"company": {}, "kpis": {}})

    # los 4 agentes, con análisis REVISADO (post-challenger) y crítica registrada
    assert set(analyses.keys()) == {"CFO", "CSO", "CRO", "Auditor"}
    assert analyses["CFO"]["summary"] == "CFO revised"
    assert critiques["CFO"] == {"weak_assumptions": ["supuesto débil"]}


# ── El Consejo delibera, y de esa conclusión nace el plan y el Roadmap ───────

def _stub_generacion(monkeypatch, plan_horizon=1):
    """Todo lo caro, apagado: solo queda la orquestación."""
    monkeypatch.setattr(orch, "run_diagnostico",
                        lambda buf: ({"CFO": {"summary": "ok"}}, {"CFO": {"weak_assumptions": []}}))
    monkeypatch.setattr(orch, "synthesize_diagnostico", lambda a: "CONCATENACIÓN")
    monkeypatch.setattr(orch, "generate_milestones", lambda *a, **k: {"items": []})
    monkeypatch.setattr(orch, "generate_quarter_plan",
                        lambda memory_buffer, kpi_labels, milestones, y, q: [])


def _db_y_plan(horizon=1):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.start_date = date(2026, 5, 1)
    plan.status = "generating"
    plan.horizon_years = horizon
    plan.genesis_session_id = None

    onboarding = MagicMock()
    onboarding.memory_buffer = {"company": {"name": "Demo"}, "kpis": {}}

    db = AsyncMock()
    db.get = AsyncMock(return_value=plan)
    result = MagicMock()
    result.scalar_one_or_none.return_value = onboarding
    result.scalars.return_value.first.return_value = None  # sin diagnóstico estratégico
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db, plan


def _genesis_de(db):
    from app.models.board_session import BoardSession
    return next((c.args[0] for c in db.add.call_args_list
                 if isinstance(c.args[0], BoardSession)), None)


_POSTURA = {
    "conclusion": "El Consejo concluye que la empresa depende de un solo cliente.",
    "prioridades": ["Diversificar clientes", "Recuperar margen", "Ordenar el gobierno"],
    "riesgos": [{"nivel": "rojo", "texto": "Liquidez"}],
    "tesis_estrategica": "Dejar de ser proveedor cautivo.",
}


@pytest.mark.asyncio
async def test_la_conclusion_del_consejo_es_el_diagnostico_y_de_ella_nace_el_roadmap(monkeypatch):
    """La conclusión ÚNICA del Consejo (no la concatenación) es el diagnóstico del plan,
    se guarda en la sesión génesis, y el Roadmap nace de ella."""
    db, plan = _db_y_plan()
    _stub_generacion(monkeypatch)
    monkeypatch.setattr(orch, "run_deliberacion_fundacional",
                        lambda analyses, critiques, mb, dcont: dict(_POSTURA))

    roadmap_args: dict = {}

    def _fake_roadmap(mb, dcont, deliberacion=None):
        roadmap_args["deliberacion"] = deliberacion
        return {"pilares": []}

    monkeypatch.setattr("app.services.ai.roadmap.generate_roadmap", _fake_roadmap)

    await orch._run_generation(str(plan.id), db)

    assert plan.status == "active"
    assert plan.diagnostico_summary == _POSTURA["conclusion"]   # no "CONCATENACIÓN"
    # el Roadmap es la traducción de la postura del Consejo
    assert roadmap_args["deliberacion"] == _POSTURA
    # la deliberación no se pierde: queda en la sesión génesis
    genesis = _genesis_de(db)
    assert genesis is not None and genesis.conclusion == _POSTURA


@pytest.mark.asyncio
@pytest.mark.parametrize("delib", [
    "boom",                                   # la deliberación revienta
    {"conclusion": "", "_fallback": True},    # la deliberación cae a su fallback
])
async def test_si_la_deliberacion_falla_el_plan_se_genera_igual(monkeypatch, delib):
    """CRÍTICO: la generación del plan tarda minutos y cuesta dinero. Si el Consejo no puede
    deliberar, se cae a la concatenación de siempre y el plan NO se pierde."""
    db, plan = _db_y_plan()
    _stub_generacion(monkeypatch)

    def _delib(analyses, critiques, mb, dcont):
        if delib == "boom":
            raise RuntimeError("boom")
        return dict(delib)

    monkeypatch.setattr(orch, "run_deliberacion_fundacional", _delib)

    roadmap_args: dict = {}

    def _fake_roadmap(mb, dcont, deliberacion=None):
        roadmap_args["deliberacion"] = deliberacion
        return {"pilares": []}

    monkeypatch.setattr("app.services.ai.roadmap.generate_roadmap", _fake_roadmap)

    await orch._run_generation(str(plan.id), db)

    assert plan.status == "active"                        # el plan se generó igual
    assert plan.diagnostico_summary == "CONCATENACIÓN"    # fallback: synthesize_diagnostico
    assert roadmap_args["deliberacion"] is None           # sin postura, roadmap como siempre
    genesis = _genesis_de(db)
    assert genesis is not None and genesis.conclusion is None
