import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.board_theme import BoardTheme
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_minuta"


def _theme(key, type_, freq, order):
    return BoardTheme(key=key, label=key.title(), type=type_,
                      every_n_sessions=freq, active=True, order_index=order)


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


def _tema(tid=0):
    return {"id": tid, "titulo": "Tema", "sintesis": "s",
            "decision": {"pregunta": "p", "opcion_a": "Acción A", "opcion_b": "Acción B",
                         "decision_tomada": None},
            "compromiso": None}


def _month(index, minuta=None, chair_agenda=None):
    m = MagicMock()
    m.id = uuid.uuid4(); m.month_index = index
    m.objectives = []; m.covered_themes = []
    m.status = "active"; m.review = None
    m.period_month = 12; m.period_year = 2026
    m.chair_agenda = chair_agenda; m.minuta = minuta
    return m


def _setup(db):
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override


@pytest.mark.asyncio
async def test_post_minuta_genera_y_guarda(monkeypatch):
    monkeypatch.setattr("app.api.v1.annual_plan.router.generate_minuta",
                        lambda items, mb, period: {"carta": "MINUTA", "temas": [_tema()]})
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)  # activo = 12
    month = _month(12)
    themes = [_theme("fin", "permanente", 1, 0)]
    onb = MagicMock(); onb.memory_buffer = {}

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = themes
    r4 = MagicMock(); r4.scalar_one_or_none.return_value = onb
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3, r4])

    _setup(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/minuta")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["generada"] is True
    assert body["carta"] == "MINUTA"
    assert month.minuta["carta"] == "MINUTA"


@pytest.mark.asyncio
async def test_get_minuta_vacia():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)
    month = _month(12, minuta=None)
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])

    _setup(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/minuta")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["generada"] is False


@pytest.mark.asyncio
async def test_decision_A_genera_compromiso():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)
    month = _month(12, minuta={"carta": "C", "temas": [_tema(0)]})
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])

    _setup(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/minuta/decision",
                             json={"tema_id": 0, "decision": "A"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["temas"][0]["decision"]["decision_tomada"] == "A"
    assert body["temas"][0]["compromiso"]["descripcion"] == "Acción A"


@pytest.mark.asyncio
async def test_decision_aplazar_sin_compromiso():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)
    month = _month(12, minuta={"carta": "C", "temas": [_tema(0)]})
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])

    _setup(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/minuta/decision",
                             json={"tema_id": 0, "decision": "aplazar"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["temas"][0]["decision"]["decision_tomada"] == "aplazar"
    assert body["temas"][0]["compromiso"] is None


@pytest.mark.asyncio
async def test_decision_invalida_422():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)
    month = _month(12, minuta={"carta": "C", "temas": [_tema(0)]})
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])

    _setup(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/minuta/decision",
                             json={"tema_id": 0, "decision": "C"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
