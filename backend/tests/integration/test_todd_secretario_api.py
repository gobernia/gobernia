import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

UID = "user_todd_sec"
R = "app.api.v1.todd_secretario.router"


def _dbov(db):
    async def o():
        yield db
    return o


async def _uov():
    return UID


def _execute_returning(rows):
    """db.execute(...) → objeto cuyo .scalars().all() devuelve `rows`."""
    res = MagicMock()
    res.scalars.return_value.all.return_value = rows
    return AsyncMock(return_value=res)


def _mock_db(rows=None):
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.execute = _execute_returning(rows or [])
    return db


def _patch_common(monkeypatch, turn, anchor=None):
    async def fake_anchor(user_id, db):
        return anchor if anchor is not None else uuid.uuid4()
    async def fake_ctx(user_id, db):
        return {"empresa": "Keting", "tablero": {"total": 0, "por_estado": {}}, "roadmap": {},
                "acuerdos_abiertos": []}
    monkeypatch.setattr(f"{R}.get_anchor_board_session_id", fake_anchor)
    monkeypatch.setattr(f"{R}.build_contexto", fake_ctx)
    monkeypatch.setattr(f"{R}.run_todd_secretario_turn", lambda mensajes, contexto: turn)


@pytest.mark.asyncio
async def test_post_persiste_usuario_y_todd_y_devuelve_reply(monkeypatch):
    _patch_common(monkeypatch, {"reply": "Tienes 0 tareas.", "accion": None})
    db = _mock_db(rows=[])  # historial vacío

    app.dependency_overrides[get_db] = _dbov(db)
    app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/todd-secretario/mensajes", json={"content": "¿cómo voy?"})
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["reply"] == "Tienes 0 tareas."
    assert r.json()["accion"] is None
    assert db.add.call_count == 2          # user + todd
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_get_lista_el_historial(monkeypatch):
    m1 = SimpleNamespace(id=uuid.uuid4(), role="user", content="hola",
                         created_at=datetime(2026, 7, 1))
    m2 = SimpleNamespace(id=uuid.uuid4(), role="assistant", content="hey",
                         created_at=datetime(2026, 7, 2))
    db = _mock_db(rows=[m1, m2])

    app.dependency_overrides[get_db] = _dbov(db)
    app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/todd-secretario/mensajes")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()
    assert [m["content"] for m in data] == ["hola", "hey"]
    assert [m["role"] for m in data] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_post_propuesta_incluye_title_y_description(monkeypatch):
    task_id = uuid.uuid4()
    _patch_common(monkeypatch, {
        "reply": "Te propongo una alternativa.",
        "accion": {"tipo": "proponer_cambio", "task_id": str(task_id),
                   "motivo": "no tengo presupuesto"},
    })
    db = _mock_db(rows=[])

    task = MagicMock(); task.id = task_id; task.title = "Contratar despacho"
    async def fake_task(tid, uid, dbx):
        return task
    async def fake_obj(t, uid, dbx):
        return ("Profesionalizar", "Keting")
    async def fake_ctx(uid, dbx):
        return "Keting · Marketing"
    monkeypatch.setattr(f"{R}._get_user_task_or_404", fake_task)
    monkeypatch.setattr(f"{R}._objetivo_empresa", fake_obj)
    monkeypatch.setattr(f"{R}._empresa_ctx", fake_ctx)
    monkeypatch.setattr(f"{R}.adapt_task", lambda *a, **k: {
        "nueva_tarea": "Usar plantillas legales", "descripcion": "Plantillas gratis",
        "por_que": "sin costo"})

    app.dependency_overrides[get_db] = _dbov(db)
    app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/todd-secretario/mensajes",
                             json={"content": "no puedo con esa, no tengo dinero"})
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    accion = r.json()["accion"]
    assert accion["tipo"] == "proponer_cambio"
    assert accion["task_id"] == str(task_id)
    assert accion["propuesta"]["title"] == "Usar plantillas legales"
    assert accion["propuesta"]["description"] == "Plantillas gratis"


@pytest.mark.asyncio
async def test_post_tarea_de_otro_usuario_devuelve_404(monkeypatch):
    task_id = uuid.uuid4()
    _patch_common(monkeypatch, {
        "reply": "Veamos.",
        "accion": {"tipo": "proponer_cambio", "task_id": str(task_id), "motivo": "no puedo"},
    })
    db = _mock_db(rows=[])

    async def fake_task(tid, uid, dbx):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    monkeypatch.setattr(f"{R}._get_user_task_or_404", fake_task)

    app.dependency_overrides[get_db] = _dbov(db)
    app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/todd-secretario/mensajes",
                             json={"content": "no puedo con esa tarea"})
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 404
