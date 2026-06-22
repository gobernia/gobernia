import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.dependencies import get_current_user_id, get_db

UID = "user_test_foda"


def _dbov(db):
    async def o():
        yield db
    return o


async def _uov():
    return UID


@pytest.mark.asyncio
async def test_get_foda_active_devuelve_matriz():
    diag = MagicMock()
    diag.content = {"foda_status": "active",
                    "foda": {"fortalezas": ["Buen portafolio"], "oportunidades": [], "debilidades": [],
                             "amenazas": [], "sintesis": "ok", "metas_priorizadas": ["Quiero más clientes"]},
                    "metas_orden": ["Quiero más clientes"]}
    res = MagicMock(); res.scalars.return_value.first.return_value = diag
    db = AsyncMock(); db.execute = AsyncMock(return_value=res)
    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/onboarding/foda")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert body["foda"]["fortalezas"] == ["Buen portafolio"]
    assert body["metas"] == ["Quiero más clientes"]


@pytest.mark.asyncio
async def test_save_metas_dispara_foda(monkeypatch):
    diag = MagicMock(); diag.content = {"sections": []}
    externo = MagicMock(); externo.state = {"factores_externos": {}}
    rdiag = MagicMock(); rdiag.scalars.return_value.first.return_value = diag
    rext = MagicMock(); rext.scalar_one_or_none.return_value = externo
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[rdiag, rext]); db.commit = AsyncMock()

    dispatched = {}
    class _Fake:
        def delay(self, uid):
            dispatched["uid"] = uid
    monkeypatch.setattr("app.tasks.foda_tasks.generate_foda_task", _Fake())

    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/metas", json={"orden": ["Quiero más clientes"]})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert diag.content["foda_status"] == "generating"
    assert dispatched.get("uid") == UID
