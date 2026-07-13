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


def _plan(status="borrador"):
    p = MagicMock()
    p.roadmap = {"vision": "V"}
    p.roadmap_status = status
    p.roadmap_validated_at = None
    return p


@pytest.mark.asyncio
async def test_patch_roadmap_bloqueado_si_esta_validado():
    """Un roadmap validado es solo lectura: PATCH devuelve 409 (hay que reabrirlo)."""
    plan = _plan("validado")
    res = MagicMock(); res.scalar_one_or_none.return_value = plan
    db = AsyncMock(); db.execute = AsyncMock(return_value=res); db.commit = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch("/api/v1/annual-plan/roadmap", json={"vision": "otra"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 409
    assert plan.roadmap == {"vision": "V"}  # no se modificó


@pytest.mark.asyncio
async def test_get_estado_devuelve_borrador_por_defecto():
    plan = _plan("borrador")
    res = MagicMock(); res.scalar_one_or_none.return_value = plan
    db = AsyncMock(); db.execute = AsyncMock(return_value=res)
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/roadmap/estado")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["status"] == "borrador"
    assert r.json()["validated_at"] is None


@pytest.mark.asyncio
async def test_reabrir_regresa_a_borrador():
    plan = _plan("validado")
    res = MagicMock(); res.scalar_one_or_none.return_value = plan
    themes_res = MagicMock(); themes_res.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[res, themes_res])
    db.commit = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/roadmap/reabrir")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["status"] == "borrador"
    assert plan.roadmap_status == "borrador"
    assert plan.roadmap_validated_at is None
