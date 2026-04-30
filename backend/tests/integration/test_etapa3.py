"""
Tests de integración de Etapa 3 — endpoint completo con mocks de DB.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_123"
MOCK_SESSION_ID = str(uuid.uuid4())

BASE_PRIORITIES = [
    {"challenge": "profitability",       "rank": 1},
    {"challenge": "commercial_growth",   "rank": 2},
    {"challenge": "talent",              "rank": 3},
]


def _mock_session(completed_stages=None):
    session = MagicMock()
    session.id = uuid.UUID(MOCK_SESSION_ID)
    session.user_id = MOCK_USER_ID
    session.completed_stages = completed_stages if completed_stages is not None else [1, 2]
    session.memory_buffer = {
        "company": {"is_family_business": False},
        "ai_context": {"company_narrative": "Empresa Demo. Equipo: 5 personas."},
        "onboarding_started_at": datetime.now(timezone.utc).isoformat(),
    }
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


@pytest.mark.asyncio
async def test_etapa3_rentabilidad_asigna_cfo():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-3",
                json={"priorities": BASE_PRIORITIES},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["lead_agent"] == "CFO"
    assert data["next_stage"] == 4
    assert 3 in data["completed_stages"]


@pytest.mark.asyncio
async def test_etapa3_cumplimiento_asigna_cro():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    priorities = [
        {"challenge": "compliance_risk",   "rank": 1},
        {"challenge": "operations",        "rank": 2},
        {"challenge": "talent",            "rank": 3},
    ]
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-3",
                json={"priorities": priorities},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["lead_agent"] == "CRO"


@pytest.mark.asyncio
async def test_etapa3_5_prioridades_validas():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    priorities = [
        {"challenge": "profitability",          "rank": 1},
        {"challenge": "commercial_growth",      "rank": 2},
        {"challenge": "talent",                 "rank": 3},
        {"challenge": "operations",             "rank": 4},
        {"challenge": "compliance_risk",        "rank": 5},
    ]
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-3",
                json={"priorities": priorities},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()["priorities_mapped"]) == 5


@pytest.mark.asyncio
async def test_etapa3_memory_buffer_contiene_agente_lider():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-3",
                json={"priorities": BASE_PRIORITIES},
            )
    finally:
        app.dependency_overrides.clear()

    buffer = session.memory_buffer
    assert len(buffer["priorities"]) == 3
    assert buffer["priorities"][0]["rank"] == 1
    assert buffer["ai_context"]["lead_agent"] == "CFO"
    assert "Prioridades estratégicas" in buffer["ai_context"]["company_narrative"]


@pytest.mark.asyncio
async def test_etapa3_sin_etapa2_falla_400():
    session = _mock_session(completed_stages=[1])  # falta etapa 2
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-3",
                json={"priorities": BASE_PRIORITIES},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "Etapa 2" in response.json()["detail"]


@pytest.mark.asyncio
async def test_etapa3_menos_de_3_prioridades_falla_422():
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-3",
                json={"priorities": [
                    {"challenge": "profitability", "rank": 1},
                    {"challenge": "talent",        "rank": 2},
                ]},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
