import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_todd"


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_turn_inicia_sesion_y_responde(monkeypatch):
    res_none = MagicMock(); res_none.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=res_none)
    db.add = MagicMock(); db.flush = AsyncMock(); db.commit = AsyncMock()

    monkeypatch.setattr(
        "app.api.v1.todd.router.run_todd_turn",
        lambda messages, state=None: {"message": "Hola, soy Todd. ¿Cómo se llama tu empresa?",
                                      "options": None, "input": "text",
                                      "state": {"areas_cubiertas": []}, "done": False},
    )

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/turn", json={"answer": None})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["message"].startswith("Hola")
    assert body["done"] is False
    assert db.add.called


@pytest.mark.asyncio
async def test_get_todd_sin_sesion_devuelve_204(monkeypatch):
    res_none = MagicMock(); res_none.scalar_one_or_none.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(return_value=res_none)
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/onboarding/todd")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_close_escribe_memory_buffer_y_marca_onboarding(monkeypatch):
    sess = MagicMock()
    sess.user_id = MOCK_USER_ID
    sess.status = "active"
    sess.state = {"company": {"name": "Keting Media"}, "areas_cubiertas": []}
    onb = MagicMock(); onb.user_id = MOCK_USER_ID
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = sess
    r2 = MagicMock(); r2.scalars.return_value.first.return_value = onb
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2]); db.commit = AsyncMock()

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/close")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert sess.status == "done"
    assert onb.memory_buffer["company"]["name"] == "Keting Media"
    assert onb.completed_stages == [1, 2, 3, 4, 5, 6, 7, 8]
