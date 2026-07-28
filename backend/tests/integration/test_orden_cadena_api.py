"""Orden del día (cadena) — documentos solicitados por prioridad aprobada.
Cada punto = una prioridad aprobada del Plan anual; sus documentos son los
`required_doc` de las tareas cuyo Objective apunta a ese pilar (dedup).
Tests con mocks (patrón de test_plan_anual_api)."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_current_user_id, get_db


def _user():
    return "user-123"


def _db_override(db):
    async def _dep():
        yield db
    return _dep


def _pilar_aprobado(indice, nombre):
    return {
        "indice": indice, "nombre": nombre, "descripcion": f"desc {nombre}",
        "objetivo": f"obj {nombre}", "kpis": [{"label": f"kpi {nombre}", "meta": ""}],
        "estrategias": [f"estrategia {nombre}"],
    }


def _plan(plan_anual=None):
    p = MagicMock()
    p.id = "plan-1"
    p.plan_anual = plan_anual
    return p


def _task(required_doc):
    t = MagicMock()
    t.required_doc = required_doc
    return t


def _mock_db(plan, task_rows=None):
    """Primer execute → _current_plan (scalar_one_or_none); segundo → tasks (.all())."""
    plan_res = MagicMock()
    plan_res.scalar_one_or_none.return_value = plan
    tasks_res = MagicMock()
    tasks_res.all.return_value = task_rows or []
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[plan_res, tasks_res])
    db.commit = AsyncMock()
    return db


async def _call(db):
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.get("/api/v1/annual-plan/orden-del-dia-cadena")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_documentos_agrupados_y_deduplicados_por_prioridad():
    plan = _plan(plan_anual={
        "anio": 2026, "aprobado": True, "aprobado_at": "2026-01-01T00:00:00+00:00",
        "pilares": [_pilar_aprobado(0, "A"), _pilar_aprobado(1, "B"), _pilar_aprobado(2, "C")],
    })
    # Pilar 0: dos tareas piden "Estado de resultados" (dedup), una pide "Contrato".
    # Pilar 1: una tarea sin required_doc (se ignora) + una con doc.
    # Pilar 2: NINGUNA tarea → documentos vacíos.
    rows = [
        (_task("Estado de resultados"), 0),
        (_task("estado de resultados "), 0),   # mismo doc, distinto case/espacio
        (_task("Contrato"), 0),
        (_task(None), 1),
        (_task("Reporte de ventas"), 1),
        (_task(""), 1),
    ]
    r = await _call(_mock_db(plan, rows))
    assert r.status_code == 200
    body = r.json()
    assert body["aprobado"] is True
    assert body["anio"] == 2026
    puntos = body["puntos"]
    assert [p["indice"] for p in puntos] == [0, 1, 2]

    # Pilar 0: "Estado de resultados" (2) antes que "Contrato" (1) — orden por n_tareas desc.
    docs0 = puntos[0]["documentos_solicitados"]
    assert [d["doc"] for d in docs0] == ["Estado de resultados", "Contrato"]
    assert docs0[0]["n_tareas"] == 2
    assert docs0[1]["n_tareas"] == 1
    assert puntos[0]["n_tareas"] == 3

    # Pilar 1: vacíos/None ignorados; solo queda el doc real.
    docs1 = puntos[1]["documentos_solicitados"]
    assert [d["doc"] for d in docs1] == ["Reporte de ventas"]
    # n_tareas cuenta TODAS las tareas del pilar (3), tengan doc o no.
    assert puntos[1]["n_tareas"] == 3

    # Pilar 2: sin tareas → documentos vacíos.
    assert puntos[2]["documentos_solicitados"] == []
    assert puntos[2]["n_tareas"] == 0
    # Los campos del pilar viajan (nombre, objetivo, kpis, estrategias).
    assert puntos[2]["nombre"] == "C"
    assert puntos[2]["objetivo"] == "obj C"
    assert puntos[2]["estrategias"] == ["estrategia C"]


@pytest.mark.asyncio
async def test_plan_no_aprobado_devuelve_puntos_vacios():
    plan = _plan(plan_anual={"anio": 2026, "aprobado": False, "pilares": []})
    r = await _call(_mock_db(plan, []))
    assert r.status_code == 200
    body = r.json()
    assert body["aprobado"] is False
    assert body["anio"] == 2026
    assert body["puntos"] == []


@pytest.mark.asyncio
async def test_sin_plan_anual_devuelve_no_aprobado():
    plan = _plan(plan_anual=None)
    r = await _call(_mock_db(plan, []))
    assert r.status_code == 200
    body = r.json()
    assert body["aprobado"] is False
    assert body["puntos"] == []


@pytest.mark.asyncio
async def test_sin_plan_404():
    r = await _call(_mock_db(None, []))
    assert r.status_code == 404
