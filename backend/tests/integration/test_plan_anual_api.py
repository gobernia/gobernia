"""Plan anual — las 3-5 prioridades aprobadas del roadmap para el año en curso.
Capa nueva encima del mismo `roadmap`. Tests con mocks (patrón de test_roadmap_validacion_api)."""
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


def _pilar(nombre):
    return {
        "nombre": nombre, "descripcion": f"desc {nombre}",
        "objetivo": f"obj {nombre}", "kpis": [{"label": f"kpi {nombre}", "meta": ""}],
        "estrategias": [f"estrategia {nombre}"],
    }


def _plan(pilares=None, plan_anual=None):
    p = MagicMock()
    p.roadmap = {"vision": "V", "pilares": pilares} if pilares is not None else {"vision": "V"}
    p.plan_anual = plan_anual
    return p


def _mock_db(plan):
    """db.execute → _current_plan devuelve el plan (un solo execute)."""
    res = MagicMock(); res.scalar_one_or_none.return_value = plan
    db = AsyncMock(); db.execute = AsyncMock(return_value=res); db.commit = AsyncMock()
    return db


async def _call(method, url, db, **kw):
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await getattr(c, method)(f"/api/v1/annual-plan/plan-anual{url}", **kw)
    finally:
        app.dependency_overrides.clear()


# ── GET ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_devuelve_pilares_disponibles_con_indices():
    plan = _plan(pilares=[_pilar("A"), _pilar("B"), _pilar("C")])
    r = await _call("get", "", _mock_db(plan))
    assert r.status_code == 200
    body = r.json()
    assert body["aprobado"] is False
    assert body["pilares_aprobados"] == []
    disp = body["pilares_disponibles"]
    assert [d["indice"] for d in disp] == [0, 1, 2]
    assert disp[0]["nombre"] == "A"
    assert disp[1]["kpis"][0]["label"] == "kpi B"


@pytest.mark.asyncio
async def test_get_sin_roadmap_devuelve_vacio():
    plan = _plan()  # roadmap sin pilares
    r = await _call("get", "", _mock_db(plan))
    assert r.status_code == 200
    body = r.json()
    assert body["pilares_disponibles"] == []
    assert body["pilares_aprobados"] == []
    assert body["aprobado"] is False


@pytest.mark.asyncio
async def test_get_sin_plan_404():
    r = await _call("get", "", _mock_db(None))
    assert r.status_code == 404


# ── Aprobar ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_aprobar_3_a_5_guarda_snapshot():
    plan = _plan(pilares=[_pilar("A"), _pilar("B"), _pilar("C"), _pilar("D")])
    r = await _call("post", "/aprobar", _mock_db(plan), json={"indices": [0, 2, 3]})
    assert r.status_code == 200
    body = r.json()
    assert body["aprobado"] is True
    assert body["aprobado_at"]
    aprobados = body["pilares_aprobados"]
    assert [a["indice"] for a in aprobados] == [0, 2, 3]
    assert [a["nombre"] for a in aprobados] == ["A", "C", "D"]
    # Persistió el snapshot en el modelo.
    assert plan.plan_anual["aprobado"] is True
    assert len(plan.plan_anual["pilares"]) == 3


@pytest.mark.asyncio
async def test_aprobar_menos_de_3_es_400():
    plan = _plan(pilares=[_pilar("A"), _pilar("B"), _pilar("C")])
    r = await _call("post", "/aprobar", _mock_db(plan), json={"indices": [0, 1]})
    assert r.status_code == 400
    assert "al menos 3" in r.json()["detail"]
    assert plan.plan_anual is None


@pytest.mark.asyncio
async def test_aprobar_mas_de_5_es_400():
    plan = _plan(pilares=[_pilar(str(i)) for i in range(7)])
    r = await _call("post", "/aprobar", _mock_db(plan), json={"indices": [0, 1, 2, 3, 4, 5]})
    assert r.status_code == 400
    assert "máximo 5" in r.json()["detail"]


@pytest.mark.asyncio
async def test_aprobar_indice_fuera_de_rango_es_400():
    plan = _plan(pilares=[_pilar("A"), _pilar("B"), _pilar("C")])
    r = await _call("post", "/aprobar", _mock_db(plan), json={"indices": [0, 1, 9]})
    assert r.status_code == 400
    assert "fuera de rango" in r.json()["detail"]


@pytest.mark.asyncio
async def test_aprobar_sin_plan_404():
    r = await _call("post", "/aprobar", _mock_db(None), json={"indices": [0, 1, 2]})
    assert r.status_code == 404


# ── Reabrir ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reabrir_pone_aprobado_false_conserva_pilares():
    snapshot = [
        {"indice": 0, "nombre": "A", "descripcion": "d", "objetivo": "o", "kpis": [], "estrategias": []},
        {"indice": 1, "nombre": "B", "descripcion": "d", "objetivo": "o", "kpis": [], "estrategias": []},
        {"indice": 2, "nombre": "C", "descripcion": "d", "objetivo": "o", "kpis": [], "estrategias": []},
    ]
    plan = _plan(
        pilares=[_pilar("A"), _pilar("B"), _pilar("C")],
        plan_anual={"anio": 2026, "aprobado": True, "aprobado_at": "2026-01-01T00:00:00+00:00", "pilares": snapshot},
    )
    r = await _call("post", "/reabrir", _mock_db(plan))
    assert r.status_code == 200
    body = r.json()
    assert body["aprobado"] is False
    # GET no expone aprobados mientras esté reabierto, pero se conservan en el modelo.
    assert body["pilares_aprobados"] == []
    assert plan.plan_anual["aprobado"] is False
    assert len(plan.plan_anual["pilares"]) == 3


@pytest.mark.asyncio
async def test_reabrir_sin_plan_anual_previo_no_falla():
    plan = _plan(pilares=[_pilar("A")], plan_anual=None)
    r = await _call("post", "/reabrir", _mock_db(plan))
    assert r.status_code == 200
    assert r.json()["aprobado"] is False
    assert plan.plan_anual["aprobado"] is False
