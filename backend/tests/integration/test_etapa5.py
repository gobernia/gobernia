"""
Tests de integración de Etapa 5 — GET kpis y POST valores.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db
from app.services.ai.kpi_engine import build_kpi_templates

MOCK_USER_ID = "user_test_kpi"
MOCK_SESSION_ID = str(uuid.uuid4())

BASE_BUFFER = {
    "company": {
        "industry": "manufacturing",
        "employees": "11-50",
        "annual_revenue": "1M-5M",
    },
    "priorities": [
        {"challenge": "profitability", "rank": 1, "activated_areas": ["finance"]},
    ],
}


def _mock_session(completed_stages=None, buffer=None):
    session = MagicMock()
    session.id = uuid.UUID(MOCK_SESSION_ID)
    session.user_id = MOCK_USER_ID
    session.completed_stages = completed_stages if completed_stages is not None else [1, 2, 3, 4]
    session.memory_buffer = buffer or BASE_BUFFER
    return session


def _db_override(session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = session

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


def _all_kpi_inputs(buffer=None):
    buf = buffer or BASE_BUFFER
    templates = build_kpi_templates(buf)
    return [
        {"key": t.key, "current_value": 50.0, "target_value": 60.0, "unknown": False}
        for t in templates
    ]


# ── GET /etapa-5/kpis ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_kpis_retorna_templates():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-5/kpis")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total_kpis"] > 0
    assert data["total_kpis"] == len(data["kpi_templates"])
    assert data["headcount_auto"] == 30


@pytest.mark.asyncio
async def test_get_kpis_sin_etapa4_falla_400():
    session = _mock_session(completed_stages=[1, 2, 3])
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-5/kpis")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_kpis_servicios_oculta_operacionales():
    buf = {
        "company": {"industry": "technology", "employees": "11-50", "annual_revenue": "1M-5M"},
        "priorities": [],
    }
    session = _mock_session(buffer=buf)
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-5/kpis")
    finally:
        app.dependency_overrides.clear()

    keys = {t["key"] for t in response.json()["kpi_templates"]}
    assert "capacity_utilization" not in keys
    assert "otif" not in keys


# ── POST /etapa-5 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_etapa5_ok():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-5",
                json={"kpis": _all_kpi_inputs()},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["next_stage"] == 6
    assert 5 in data["completed_stages"]
    assert isinstance(data["kpi_results"], list)
    assert len(data["kpi_results"]) > 0


@pytest.mark.asyncio
async def test_submit_etapa5_genera_alerta_concentracion():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    templates = build_kpi_templates(BASE_BUFFER)
    kpis = [
        {"key": t.key, "current_value": 65.0 if t.key == "top5_concentration" else 50.0,
         "target_value": None, "unknown": False}
        for t in templates
    ]

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-5",
                json={"kpis": kpis},
            )
    finally:
        app.dependency_overrides.clear()

    data = response.json()
    assert len(data["alerts"]) > 0
    assert any("top 5" in a.lower() or "concentración" in a.lower() for a in data["alerts"])


@pytest.mark.asyncio
async def test_submit_etapa5_gap_count_correcto():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    templates = build_kpi_templates(BASE_BUFFER)
    # Marcar 2 como unknown
    kpis = []
    unknown_count = 0
    for i, t in enumerate(templates):
        is_unknown = i < 2
        if is_unknown:
            unknown_count += 1
        kpis.append({"key": t.key, "current_value": None, "target_value": None, "unknown": is_unknown})

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-5",
                json={"kpis": kpis},
            )
    finally:
        app.dependency_overrides.clear()

    data = response.json()
    assert data["gap_count"] >= unknown_count


@pytest.mark.asyncio
async def test_submit_etapa5_memory_buffer_actualizado():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-5",
                json={"kpis": _all_kpi_inputs()},
            )
    finally:
        app.dependency_overrides.clear()

    buf = session.memory_buffer
    assert "kpis" in buf
    assert "kpi_alerts" in buf


@pytest.mark.asyncio
async def test_submit_etapa5_sin_etapa4_falla_400():
    session = _mock_session(completed_stages=[1, 2, 3])
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-5",
                json={"kpis": _all_kpi_inputs()},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
