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
async def test_close_escribe_memory_buffer_y_dispara_diagnostico(monkeypatch):
    sess = MagicMock()
    sess.user_id = MOCK_USER_ID
    sess.status = "active"
    sess.state = {"company": {"name": "Keting Media"}, "areas_cubiertas": [],
                  "hallazgos": {"financiero": [{"tipo": "debilidad", "texto": "Márgenes"}]}}
    onb = MagicMock(); onb.user_id = MOCK_USER_ID
    # 1ª query: ToddSession; 2ª: OnboardingSession; 3ª: diagnóstico previo (none)
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = sess
    r2 = MagicMock(); r2.scalars.return_value.first.return_value = onb
    r3 = MagicMock(); r3.scalars.return_value.first.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])
    db.add = MagicMock(); db.flush = AsyncMock(); db.commit = AsyncMock()

    dispatched = {}
    class _FakeTask:
        def delay(self, diag_id):
            dispatched["id"] = diag_id
    monkeypatch.setattr("app.tasks.diagnostico_tasks.generate_diagnostico_task", _FakeTask())

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
    assert db.add.called
    assert "id" in dispatched


@pytest.mark.asyncio
async def test_edit_rehacer_trunca_posteriores(monkeypatch):
    sess = MagicMock()
    sess.user_id = MOCK_USER_ID
    sess.status = "active"
    sess.state = {"areas_cubiertas": ["estrategia"]}
    sess.messages = [
        {"role": "todd", "text": "¿Nombre?", "options": None},
        {"role": "user", "text": "Keting", "options": None},
        {"role": "todd", "text": "¿Industria?", "options": None},
        {"role": "user", "text": "Comercio", "options": None},
    ]
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = sess
    db = AsyncMock(); db.execute = AsyncMock(return_value=r1); db.commit = AsyncMock()

    monkeypatch.setattr(
        "app.api.v1.todd.router.run_todd_edit",
        lambda messages, edited_question, new_answer, state=None: {
            "message": "Con ese cambio, repasemos: ¿industria?", "options": None,
            "input": "text", "state": {"areas_cubiertas": ["estrategia"]},
            "done": False, "reanudar_desde": "rehacer"},
    )

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/edit", json={"answer_index": 1, "nueva_respuesta": "Keting Media"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert sess.messages[1]["text"] == "Keting Media"
    assert sess.messages[-1]["role"] == "todd"
    assert all(m["text"] != "Comercio" for m in sess.messages)


@pytest.mark.asyncio
async def test_edit_continuar_conserva_posteriores(monkeypatch):
    sess = MagicMock()
    sess.user_id = MOCK_USER_ID
    sess.status = "active"
    sess.state = {"areas_cubiertas": ["estrategia", "comercial"]}
    sess.messages = [
        {"role": "todd", "text": "¿Nombre?", "options": None},
        {"role": "user", "text": "Keting", "options": None},
        {"role": "todd", "text": "¿Industria?", "options": None},
        {"role": "user", "text": "Software", "options": None},
    ]
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = sess
    db = AsyncMock(); db.execute = AsyncMock(return_value=r1); db.commit = AsyncMock()

    monkeypatch.setattr(
        "app.api.v1.todd.router.run_todd_edit",
        lambda messages, edited_question, new_answer, state=None: {
            "message": "Perfecto. ¿Tienen misión y visión?", "options": ["Sí", "No"],
            "input": "single_choice", "state": {"areas_cubiertas": ["estrategia", "comercial"]},
            "done": False, "reanudar_desde": "continuar"},
    )

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/edit", json={"answer_index": 1, "nueva_respuesta": "Keting Media"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert sess.messages[1]["text"] == "Keting Media"
    assert any(m["text"] == "Software" for m in sess.messages)
    assert sess.messages[-1]["text"].startswith("Perfecto")
