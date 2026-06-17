import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_dl"


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


def _evidence():
    ev = MagicMock()
    ev.id = uuid.uuid4()
    ev.action_task_id = uuid.uuid4()
    ev.s3_key = "documents/a/b/c.pdf"
    return ev


@pytest.mark.asyncio
async def test_download_devuelve_url_prefirmada(monkeypatch):
    ev = _evidence()

    async def fake_owned(tid, uid, db):
        return MagicMock()
    monkeypatch.setattr("app.api.v1.evidence.router._get_user_task_or_404", fake_owned)
    monkeypatch.setattr("app.api.v1.evidence.router.presigned_get_url", lambda key: "https://signed/x")

    result = MagicMock()
    result.scalar_one_or_none.return_value = ev
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/v1/evidence/{ev.id}/download")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["url"] == "https://signed/x"


@pytest.mark.asyncio
async def test_download_404_sin_s3(monkeypatch):
    ev = _evidence()

    async def fake_owned(tid, uid, db):
        return MagicMock()
    monkeypatch.setattr("app.api.v1.evidence.router._get_user_task_or_404", fake_owned)
    monkeypatch.setattr("app.api.v1.evidence.router.presigned_get_url", lambda key: None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = ev
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/v1/evidence/{ev.id}/download")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_download_404_evidencia_inexistente(monkeypatch):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/v1/evidence/{uuid.uuid4()}/download")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
