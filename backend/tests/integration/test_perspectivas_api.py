import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_current_user_id, get_db


def _user_override():
    return "user-123"


def _db_override(db):
    async def _dep():
        yield db
    return _dep


@pytest.mark.asyncio
async def test_invite_crea_token_y_url():
    db = AsyncMock()

    # Mock flush to set created_at on the object
    async def mock_flush():
        # Get the last added object and set created_at
        pass

    db.add = MagicMock()
    db.flush = AsyncMock(side_effect=mock_flush)
    db.commit = AsyncMock()

    # Intercept the add call to set created_at after flush
    original_add = db.add
    def mock_add(obj):
        obj.created_at = datetime.now()
        return original_add(obj)

    db.add = mock_add

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/perspectivas/invite", json={"role": "cliente"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "cliente"
    assert len(body["token"]) >= 16
    assert body["token"] in body["url"]


@pytest.mark.asyncio
async def test_invite_rechaza_rol_invalido():
    db = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/perspectivas/invite", json={"role": "extraterrestre"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
