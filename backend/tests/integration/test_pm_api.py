from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.compromiso import Compromiso
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_pm"


def _comp(token="t1", status="abierto", avances=None, user_id=MOCK_USER_ID, fecha=None):
    return Compromiso(user_id=user_id, descripcion="Hacer X", status=status,
                      token=token, avances=avances if avances is not None else [],
                      fecha_compromiso=fecha)


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_list_compromisos():
    c = _comp(token="t1")
    r1 = MagicMock(); r1.scalars.return_value.all.return_value = [c]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/v1/pm/compromisos")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["token"] == "t1"
    assert body[0]["nudge"] == "al_dia"


@pytest.mark.asyncio
async def test_patch_responsable():
    c = _comp(token="t1")
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = c
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(f"/api/v1/pm/compromisos/{c.id}",
                                   json={"responsable_email": "a@b.com"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["responsable_email"] == "a@b.com"


@pytest.mark.asyncio
async def test_patch_ajeno_404():
    c = _comp(token="t1", user_id="otro")
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = c
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(f"/api/v1/pm/compromisos/{c.id}", json={"responsable_email": "x@y.com"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_publico_y_404():
    c = _comp(token="t1")
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = c
    r2 = MagicMock(); r2.scalar_one_or_none.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])
    app.dependency_overrides[get_db] = _db_override(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ok = await client.get("/api/v1/pm/c/t1")
            bad = await client.get("/api/v1/pm/c/nope")
    finally:
        app.dependency_overrides.clear()
    assert ok.status_code == 200
    assert ok.json()["descripcion"] == "Hacer X"
    assert "token" not in ok.json()
    assert bad.status_code == 404


@pytest.mark.asyncio
async def test_avance_actualiza_status():
    c = _comp(token="t1", status="abierto", avances=[])
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = c
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1])
    app.dependency_overrides[get_db] = _db_override(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/v1/pm/c/t1/avance",
                                  json={"pct": 100, "nota": "listo", "evidencia_url": "http://x"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completado"
    assert len(body["avances"]) == 1
    assert body["avances"][0]["pct"] == 100
