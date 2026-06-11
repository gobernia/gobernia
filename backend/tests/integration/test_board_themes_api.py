import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_themes"


def _plan():
    p = MagicMock()
    p.id = uuid.uuid4()
    p.user_id = MOCK_USER_ID
    p.status = "active"
    p.start_date = date.today()
    return p


def _theme(label="Finanzas", type_="permanente", freq=1):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.key = "finanzas"
    t.label = label
    t.type = type_
    t.every_n_sessions = freq
    t.active = True
    t.is_default = True
    t.order_index = 0
    return t


def _db_for_list(plan, themes):
    """_current_plan usa scalar_one_or_none; list usa scalars().all()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = plan
    result.scalars.return_value.all.return_value = themes
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_list_themes_returns_themes():
    db = _db_for_list(_plan(), [_theme(), _theme("Riesgos")])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/themes")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert r.json()[0]["label"] == "Finanzas"


@pytest.mark.asyncio
async def test_list_themes_404_when_no_plan():
    db = _db_for_list(None, [])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/themes")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_theme_404_when_not_owned():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # _load_owned_theme no encuentra
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/annual-plan/themes/{uuid.uuid4()}", json={"active": False})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_theme_validation_422():
    db = _db_for_list(_plan(), [])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/themes",
                             json={"label": "X", "type": "cobertura", "every_n_sessions": 5})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_generate_seeds_themes(monkeypatch):
    """generate_plan crea el plan y siembra los temas por defecto."""
    seeded = {"called": False, "count": 0}

    async def fake_seed(db, plan_id):
        seeded["called"] = True
        seeded["count"] = 13
        return 13

    monkeypatch.setattr("app.api.v1.annual_plan.router.seed_default_themes", fake_seed)

    onb = MagicMock(); onb.completed_stages = [1, 2, 3, 4, 5, 6, 7, 8]  # onboarding completo
    onb.memory_buffer = {"company": {"name": "ACME"},
                         "kpis": {"finance": [{"label": "Margen", "current_value": 12.0, "unknown": False}]}}
    onb_result = MagicMock(); onb_result.scalar_one_or_none.return_value = onb
    plan_result = MagicMock(); plan_result.scalar_one_or_none.return_value = None  # no hay plan previo
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[onb_result, plan_result])
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    def boom(*a, **k):
        raise RuntimeError("no celery")
    monkeypatch.setattr("app.tasks.annual_plan_tasks.generate_annual_plan_task.delay", boom)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/api/v1/annual-plan/generate")
    finally:
        app.dependency_overrides.clear()
    assert seeded["called"] is True


@pytest.mark.asyncio
async def test_generate_requires_onboarding_completo():
    """generate_plan bloquea (400) si el onboarding no tiene las 8 etapas."""
    onb = MagicMock(); onb.completed_stages = [1, 2, 3]  # incompleto
    onb_result = MagicMock(); onb_result.scalar_one_or_none.return_value = onb
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[onb_result])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/generate")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_generate_requires_onboarding_existe():
    """generate_plan bloquea (400) si el usuario no tiene sesión de onboarding."""
    onb_result = MagicMock(); onb_result.scalar_one_or_none.return_value = None  # sin sesión
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[onb_result])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/generate")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_generate_requires_kpis_con_valor():
    """generate_plan bloquea (400) si los KPIs están en 'no sé' (sin valor)."""
    onb = MagicMock(); onb.completed_stages = [1, 2, 3, 4, 5, 6, 7, 8]
    onb.memory_buffer = {"company": {"name": "ACME"},
                         "kpis": {"finance": [{"label": "Margen", "current_value": None, "unknown": True}]}}
    onb_result = MagicMock(); onb_result.scalar_one_or_none.return_value = onb
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[onb_result])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/generate")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400
    assert "KPIs sin valor" in r.json()["detail"]
