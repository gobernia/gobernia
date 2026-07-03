import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_db


def _db_override(db):
    async def _dep():
        yield db
    return _dep


@pytest.mark.asyncio
async def test_get_token_invalido_da_404():
    db = AsyncMock()
    res = MagicMock(); res.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=res)
    app.dependency_overrides[get_db] = _db_override(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/perspectiva/token-inexistente")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_token_valido_devuelve_rol_y_empresa(monkeypatch):
    inv = MagicMock()
    inv.role = "cliente"; inv.messages = []; inv.status = "pending"
    res_inv = MagicMock(); res_inv.scalar_one_or_none.return_value = inv
    onb = MagicMock(); onb.memory_buffer = {"company": {"name": "Keting Media"}}
    res_onb = MagicMock(); res_onb.scalars.return_value.first.return_value = onb
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[res_inv, res_onb])
    app.dependency_overrides[get_db] = _db_override(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/perspectiva/tok-abc")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "cliente"
    assert "Keting Media" in body["company_name"]
    assert body["done"] is False
