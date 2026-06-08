import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_evidence"
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _task(status="pendiente"):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.status = status
    return t


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_upload_evidence_creates_and_advances_status(monkeypatch):
    task = _task(status="pendiente")

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.evidence.router._get_user_task_or_404", fake_owned)

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda o: setattr(o, "created_at", NOW))

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                f"/api/v1/tasks/{task.id}/evidence",
                files={"file": ("acta.pdf", b"%PDF-1.4 data", "application/pdf")},
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["filename"] == "acta.pdf"
    assert db.add.called
    assert task.status == "en_progreso"


@pytest.mark.asyncio
async def test_upload_evidence_rejects_bad_extension(monkeypatch):
    task = _task()

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.evidence.router._get_user_task_or_404", fake_owned)

    db = AsyncMock()
    db.add = MagicMock(); db.flush = AsyncMock(); db.commit = AsyncMock(); db.refresh = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                f"/api/v1/tasks/{task.id}/evidence",
                files={"file": ("malo.exe", b"x", "application/octet-stream")},
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_evidence(monkeypatch):
    task = _task()

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.evidence.router._get_user_task_or_404", fake_owned)

    ev = MagicMock()
    ev.id = uuid.uuid4(); ev.action_task_id = task.id; ev.filename = "x.pdf"
    ev.content_type = "application/pdf"; ev.size_bytes = 5; ev.created_at = NOW

    result = MagicMock()
    result.scalars.return_value.all.return_value = [ev]
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/v1/tasks/{task.id}/evidence")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["filename"] == "x.pdf"
