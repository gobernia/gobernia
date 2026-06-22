import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.dependencies import get_current_user_id, get_db

UID = "user_test_exp"


def _dbov(db):
    async def o():
        yield db
    return o


async def _uov():
    return UID


@pytest.mark.asyncio
async def test_explicacion_cacheada_no_regenera(monkeypatch):
    task = MagicMock()
    task.id = uuid.uuid4(); task.title = "Lanzar campaña"; task.objective_id = None
    task.kpi_ref = None; task.explicacion = {"tiempo": "~2 h", "dificultad": "Media",
                                             "que_es": "ya", "como": ["a"]}

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.action_plans.router._get_user_task_or_404", fake_owned)
    called = {"n": 0}
    monkeypatch.setattr("app.api.v1.action_plans.router.generate_explicacion",
                        lambda *a, **k: (called.__setitem__("n", called["n"] + 1) or {}))

    db = AsyncMock()
    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/v1/tasks/{task.id}/explicacion")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["que_es"] == "ya"
    assert called["n"] == 0   # cacheada → no llamó al generador


@pytest.mark.asyncio
async def test_explicacion_genera_y_guarda(monkeypatch):
    task = MagicMock()
    task.id = uuid.uuid4(); task.title = "Lanzar campaña"; task.objective_id = None
    task.kpi_ref = None; task.explicacion = None

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.action_plans.router._get_user_task_or_404", fake_owned)
    monkeypatch.setattr("app.api.v1.action_plans.router.generate_explicacion",
                        lambda *a, **k: {"tiempo": "~3 h", "dificultad": "Media", "que_es": "x", "como": ["p1"]})

    db = AsyncMock(); db.commit = AsyncMock()
    # _objetivo_empresa loads Objective + onboarding → db.execute used; make it return None-ish
    res = MagicMock(); res.scalar_one_or_none.return_value = None
    res.scalars.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=res)

    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/v1/tasks/{task.id}/explicacion")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["que_es"] == "x"
    assert task.explicacion["que_es"] == "x"   # guardada en la tarea
