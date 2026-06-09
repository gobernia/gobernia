import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.action_plan import ActionTask
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_gate"
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _task(status="en_progreso"):
    return ActionTask(
        id=uuid.uuid4(), plan_id=uuid.uuid4(), title="Acuerdo",
        status=status, priority="media", order_index=0,
    )


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_validar_sin_evidencia_409(monkeypatch):
    task = _task()

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.action_plans.router._get_user_task_or_404", fake_owned)

    result = MagicMock(); result.scalar.return_value = 0
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock(); db.commit = AsyncMock(); db.refresh = AsyncMock()

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/tasks/{task.id}", json={"status": "completada"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_validar_con_evidencia_200(monkeypatch):
    task = _task()

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.action_plans.router._get_user_task_or_404", fake_owned)

    result = MagicMock(); result.scalar.return_value = 1
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock(); db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda o: (setattr(o, "created_at", NOW), setattr(o, "updated_at", NOW)))

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/tasks/{task.id}", json={"status": "completada"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["status"] == "completada"
    assert task.status == "completada"


@pytest.mark.asyncio
async def test_cambio_no_validar_no_bloquea(monkeypatch):
    task = _task(status="pendiente")

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.action_plans.router._get_user_task_or_404", fake_owned)

    db = AsyncMock(); db.execute = AsyncMock()
    db.flush = AsyncMock(); db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda o: (setattr(o, "created_at", NOW), setattr(o, "updated_at", NOW)))

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/tasks/{task.id}", json={"status": "en_progreso"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    db.execute.assert_not_called()
