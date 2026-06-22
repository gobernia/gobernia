import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.dependencies import get_current_user_id, get_db

UID = "user_test_ext"


def _dbov(db):
    async def o():
        yield db
    return o


async def _uov():
    return UID


@pytest.mark.asyncio
async def test_externo_turn_crea_sesion_fase_externo(monkeypatch):
    res_none = MagicMock(); res_none.scalar_one_or_none.return_value = None
    res_diag = MagicMock(); res_diag.scalars.return_value.first.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[res_none, res_diag])
    db.add = MagicMock(); db.flush = AsyncMock(); db.commit = AsyncMock()
    monkeypatch.setattr("app.api.v1.todd.router.run_externo_turn",
        lambda messages, state, ctx: {"message": "¿Te afectan los cambios fiscales?",
            "options": ["Sí", "No"], "input": "single_choice",
            "state": {"areas_cubiertas": ["economicos"]}, "done": False})
    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/externo/turn", json={"answer": None})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["areas_cubiertas"] == ["economicos"]
    assert db.add.called


@pytest.mark.asyncio
async def test_get_metas_devuelve_lista(monkeypatch):
    res = MagicMock(); res.scalar_one_or_none.return_value = None
    res_diag = MagicMock(); res_diag.scalars.return_value.first.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(return_value=res)
    # _current(interno), _current(externo), _diagnostico_ctx -> 3 execute
    db.execute = AsyncMock(side_effect=[res, res, res_diag])
    monkeypatch.setattr("app.api.v1.todd.router.generar_metas",
        lambda ctx, i, e: ["Quiero más clientes", "Quiero reducir costos"])
    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/onboarding/todd/metas")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["metas"][0] == "Quiero más clientes"


@pytest.mark.asyncio
async def test_save_metas_guarda_en_content(monkeypatch):
    diag = MagicMock(); diag.content = {"sections": []}
    externo = MagicMock(); externo.state = {"factores_externos": {"economicos": [{"tipo": "amenaza", "texto": "impuestos"}]}}
    rdiag = MagicMock(); rdiag.scalars.return_value.first.return_value = diag
    rext = MagicMock(); rext.scalar_one_or_none.return_value = externo
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[rdiag, rext]); db.commit = AsyncMock()
    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/metas", json={"orden": ["Quiero más clientes", "Quiero reducir costos"]})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert diag.content["metas_orden"][0] == "Quiero más clientes"
    assert diag.content["factores_externos"]["economicos"][0]["texto"] == "impuestos"
