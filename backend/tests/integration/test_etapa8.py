"""
Tests de integración de Etapa 8 — GET options y POST configuración de agentes.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db
from app.schemas.etapa8 import VALID_AGENTS

MOCK_USER_ID = "user_test_vision"
MOCK_SESSION_ID = str(uuid.uuid4())

BASE_BUFFER = {
    "company": {"industry": "manufacturing"},
    "ai_context": {"company_narrative": "Empresa Demo. Diagnóstico completo."},
}


def _mock_session(completed_stages=None, buffer=None):
    session = MagicMock()
    session.id = uuid.UUID(MOCK_SESSION_ID)
    session.user_id = MOCK_USER_ID
    session.completed_stages = (
        completed_stages if completed_stages is not None else [1, 2, 3, 4, 5, 6, 7]
    )
    session.memory_buffer = dict(buffer or BASE_BUFFER)
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


def _valid_body():
    return {
        "vision_statement": "Ser la empresa referente de gobierno corporativo en México en los próximos 5 años.",
        "main_goals": ["Duplicar ingresos", "Apertura internacional", "Consolidar gobierno"],
        "board_expectations": {
            "session_frequency": "monthly",
            "priority_topics": ["Finanzas", "Crecimiento", "Riesgos"],
            "success_definition": "Alcanzar todos los KPIs definidos y mantener el Governance Score sobre 80.",
        },
        "agent_configs": [
            {"agent": "CFO", "tone": "formal", "alert_sensitivity": "high"},
            {"agent": "CSO", "tone": "strategic", "alert_sensitivity": "medium"},
            {"agent": "CRO", "tone": "direct", "alert_sensitivity": "high"},
            {"agent": "Auditor", "tone": "collaborative", "alert_sensitivity": "medium"},
        ],
    }


# ── GET /etapa-8/options ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_options_retorna_estructura():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-8/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert set(data["agents"]) == VALID_AGENTS
    assert "formal" in data["tones"]
    assert "high" in data["sensitivities"]
    assert "monthly" in data["frequencies"]


@pytest.mark.asyncio
async def test_get_options_sin_etapa7_falla_400():
    session = _mock_session(completed_stages=[1, 2, 3, 4, 5, 6])
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-8/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


# ── POST /etapa-8 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_etapa8_ok():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-8",
                json=_valid_body(),
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["next_stage"] == 9
    assert 8 in data["completed_stages"]
    assert len(data["agent_configs"]) == 4
    assert data["session_frequency"] == "monthly"


@pytest.mark.asyncio
async def test_submit_etapa8_memory_buffer_actualizado():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-8",
                json=_valid_body(),
            )
    finally:
        app.dependency_overrides.clear()

    buf = session.memory_buffer
    assert "vision" in buf
    assert "agent_configs" in buf
    assert set(buf["agent_configs"].keys()) == VALID_AGENTS
    assert "VISIÓN" in buf["ai_context"]["company_narrative"]


@pytest.mark.asyncio
async def test_submit_etapa8_agente_duplicado_falla_422():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    body = _valid_body()
    body["agent_configs"][1]["agent"] = "CFO"  # duplicar CFO

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-8",
                json=body,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_etapa8_faltan_agentes_falla_422():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    body = _valid_body()
    body["agent_configs"] = body["agent_configs"][:2]  # solo CFO y CSO

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-8",
                json=body,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_etapa8_sin_etapa7_falla_400():
    session = _mock_session(completed_stages=[1, 2, 3, 4, 5, 6])
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-8",
                json=_valid_body(),
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_submit_etapa8_agent_configs_tienen_labels():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-8",
                json=_valid_body(),
            )
    finally:
        app.dependency_overrides.clear()

    configs = response.json()["agent_configs"]
    for c in configs:
        assert "tone_label" in c
        assert len(c["tone_label"]) > 0
        assert "sensitivity_label" in c
