from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER = "user_diag_test"


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER


@pytest.mark.asyncio
async def test_generate_400_si_faltan_datos():
    onb = MagicMock(); onb.memory_buffer = {"company": {"name": "ACME"}}
    onb_res = MagicMock(); onb_res.scalars.return_value.first.return_value = onb
    db = AsyncMock(); db.execute = AsyncMock(return_value=onb_res)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/diagnostico/generate")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400
    assert "completar" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_status_404_si_no_hay():
    none_res = MagicMock(); none_res.scalars.return_value.first.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(return_value=none_res); db.commit = AsyncMock()

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/diagnostico/status")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
