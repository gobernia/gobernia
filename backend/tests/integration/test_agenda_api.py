import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.board_theme import BoardTheme
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_agenda"


def _theme(key, type_, freq, order):
    return BoardTheme(key=key, label=key.title(), type=type_,
                      every_n_sessions=freq, active=True, order_index=order)


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


def _month(index, chair_agenda=None):
    m = MagicMock()
    m.id = uuid.uuid4(); m.month_index = index
    m.objectives = []; m.covered_themes = []
    m.status = "active"; m.review = None
    m.period_month = 12; m.period_year = 2026
    m.chair_agenda = chair_agenda
    return m


@pytest.mark.asyncio
async def test_get_agenda_determinista():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1); plan.horizon_years = 1  # mes activo = 12 (cap a 12 meses)
    month = _month(1)  # no es el activo -> active_month None -> determinista
    themes = [_theme("fin", "permanente", 1, 0)]

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = themes
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/agenda")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["curada"] is False
    assert isinstance(body["items"], list)
    assert any(i["detector"] == "TemaDeCobertura" for i in body["items"])
    assert body["items"][0]["orden"] == 1


@pytest.mark.asyncio
async def test_get_agenda_curada():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1); plan.horizon_years = 1  # mes activo = 12 (cap a 12 meses)
    stored = {"carta": "Hola del Chair", "items": [
        {"orden": 1, "titulo": "X", "area": "kpi", "detector": "DesviaciónKPI",
         "impacto": "alto", "urgencia": "media", "racional": "r", "evidencia": ["e"], "score": 30.0}]}
    month = _month(12, chair_agenda=stored)  # ES el mes activo
    themes = [_theme("fin", "permanente", 1, 0)]

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = themes
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/agenda")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["curada"] is True
    assert body["carta"] == "Hola del Chair"
    assert body["items"][0]["titulo"] == "X"


@pytest.mark.asyncio
async def test_post_chair_guarda_y_devuelve_curada(monkeypatch):
    def fake_chair(agenda, mb, period):
        return {"carta": "CARTA", "items": [
            {"orden": 1, "titulo": "C", "area": "kpi", "detector": "DesviaciónKPI",
             "impacto": "alto", "urgencia": "media", "racional": "prosa", "evidencia": ["e"], "score": 30.0}]}
    monkeypatch.setattr("app.api.v1.annual_plan.router.chair_curate_agenda", fake_chair)

    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1); plan.horizon_years = 1  # activo = 12 (cap a 12 meses)
    month = _month(12)  # es el activo
    themes = [_theme("fin", "permanente", 1, 0)]
    onb = MagicMock(); onb.memory_buffer = {}

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan          # _current_plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month] # months
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = themes  # themes
    r4 = MagicMock(); r4.scalar_one_or_none.return_value = onb           # onboarding
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3, r4])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/agenda/chair")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["curada"] is True
    assert body["carta"] == "CARTA"
    assert body["items"][0]["titulo"] == "C"
    assert month.chair_agenda["carta"] == "CARTA"  # se persistió en el mes activo
