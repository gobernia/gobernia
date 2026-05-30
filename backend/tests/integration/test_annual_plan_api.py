"""Integración del API de plan anual — lectura, estado y CRUD."""
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_plan"


def _mock_plan():
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.user_id = MOCK_USER_ID
    plan.title = "Plan 12 meses"
    plan.start_date = date.today()   # mes activo siempre = 1 (test estable en cualquier fecha)
    plan.status = "active"
    plan.diagnostico_summary = "Diag"
    plan.genesis_session_id = None
    plan.months = []
    return plan


def _db_override(scalar_value):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_value

    async def override():
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        yield db

    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_get_status_returns_active():
    plan = _mock_plan()
    app.dependency_overrides[get_db] = _db_override(plan)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/status")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert body["active_month_index"] == 1


@pytest.mark.asyncio
async def test_get_status_404_when_no_plan():
    app.dependency_overrides[get_db] = _db_override(None)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/status")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_annual_plan_returns_payload():
    plan = _mock_plan()
    app.dependency_overrides[get_db] = _db_override(plan)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Plan 12 meses"
    assert body["status"] == "active"
    assert body["months"] == []


@pytest.mark.asyncio
async def test_etapa8_encola_generacion(monkeypatch):
    """Al cerrar etapa 8 sin plan previo, se encola generate_annual_plan."""
    import app.tasks.annual_plan_tasks as orch

    called = {}
    monkeypatch.setattr(orch.generate_annual_plan_task, "delay",
                        lambda pid: called.setdefault("pid", pid))

    onboarding = MagicMock()
    onboarding.id = uuid.uuid4()
    onboarding.user_id = MOCK_USER_ID
    onboarding.completed_stages = [1, 2, 3, 4, 5, 6, 7]
    onboarding.memory_buffer = {"company": {"industry": "manufacturing"},
                                "ai_context": {"company_narrative": "Demo"}}

    def _make_result(val):
        r = MagicMock(); r.scalar_one_or_none.return_value = val; return r

    async def override_db():
        db = AsyncMock()
        # 1ª execute = _get_session_or_404 → onboarding ; 2ª = ¿existe AnnualPlan? → None (encola)
        seq = [_make_result(onboarding), _make_result(None)]
        db.execute = AsyncMock(side_effect=lambda *a, **k: seq.pop(0) if seq else _make_result(None))
        db.flush = AsyncMock(); db.commit = AsyncMock(); db.rollback = AsyncMock()
        db.add = MagicMock()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = _user_override
    body = {
        "vision_statement": "Ser referente de gobierno corporativo en México en 5 años.",
        "main_goals": ["Duplicar ingresos", "Internacionalizar", "Consolidar gobierno"],
        "board_expectations": {"session_frequency": "monthly",
                               "priority_topics": ["Finanzas"], "success_definition": "KPIs y score >80."},
        "agent_configs": [
            {"agent": "CFO", "tone": "formal", "alert_sensitivity": "high"},
            {"agent": "CSO", "tone": "strategic", "alert_sensitivity": "medium"},
            {"agent": "CRO", "tone": "direct", "alert_sensitivity": "high"},
            {"agent": "Auditor", "tone": "collaborative", "alert_sensitivity": "medium"},
        ],
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/v1/onboarding/{onboarding.id}/etapa-8", json=body)
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert "pid" in called      # se encoló la generación


@pytest.mark.asyncio
async def test_etapa8_no_rompe_si_cola_caida(monkeypatch):
    """Si encolar la generación falla (Redis/Celery caído), el onboarding se completa igual (200)."""
    import app.tasks.annual_plan_tasks as orch

    def _boom(pid):
        raise RuntimeError("broker unavailable")
    monkeypatch.setattr(orch.generate_annual_plan_task, "delay", _boom)

    onboarding = MagicMock()
    onboarding.id = uuid.uuid4()
    onboarding.user_id = MOCK_USER_ID
    onboarding.completed_stages = [1, 2, 3, 4, 5, 6, 7]
    onboarding.memory_buffer = {"company": {"industry": "manufacturing"},
                                "ai_context": {"company_narrative": "Demo"}}

    def _make_result(val):
        r = MagicMock(); r.scalar_one_or_none.return_value = val; return r

    async def override_db():
        db = AsyncMock()
        seq = [_make_result(onboarding), _make_result(None)]
        db.execute = AsyncMock(side_effect=lambda *a, **k: seq.pop(0) if seq else _make_result(None))
        db.flush = AsyncMock(); db.commit = AsyncMock(); db.rollback = AsyncMock()
        db.add = MagicMock()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = _user_override
    body = {
        "vision_statement": "Ser referente de gobierno corporativo en México en 5 años.",
        "main_goals": ["Duplicar ingresos", "Internacionalizar", "Consolidar gobierno"],
        "board_expectations": {"session_frequency": "monthly",
                               "priority_topics": ["Finanzas"], "success_definition": "KPIs y score >80."},
        "agent_configs": [
            {"agent": "CFO", "tone": "formal", "alert_sensitivity": "high"},
            {"agent": "CSO", "tone": "strategic", "alert_sensitivity": "medium"},
            {"agent": "CRO", "tone": "direct", "alert_sensitivity": "high"},
            {"agent": "Auditor", "tone": "collaborative", "alert_sensitivity": "medium"},
        ],
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/v1/onboarding/{onboarding.id}/etapa-8", json=body)
    finally:
        app.dependency_overrides.clear()

    # El onboarding se completa pese al fallo de la cola (best-effort, no rompe).
    assert r.status_code == 200
    assert 8 in r.json()["completed_stages"]
