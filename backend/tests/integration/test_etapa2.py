"""
Tests de integración de Etapa 2 — endpoint completo con mocks de DB.
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

BASE_TEAM = [
    {"name": "Carlos García", "role": "ceo", "is_family": False, "makes_key_decisions": True, "email": "carlos@empresa.com"},
    {"name": "Ana López",     "role": "cfo", "is_family": False, "makes_key_decisions": False},
    {"name": "Pedro Ruiz",    "role": "commercial", "is_family": False, "makes_key_decisions": False},
    {"name": "María Torres",  "role": "operations", "is_family": False, "makes_key_decisions": False},
    {"name": "Luis Méndez",   "role": "hr", "is_family": False, "makes_key_decisions": False},
]


def _mock_session(completed_stages=None, is_family_business=False):
    session = MagicMock()
    session.id = uuid.UUID(MOCK_SESSION_ID)
    session.user_id = MOCK_USER_ID
    session.completed_stages = completed_stages if completed_stages is not None else [1]
    session.memory_buffer = {
        "company": {"is_family_business": is_family_business},
        "ai_context": {"company_narrative": "Empresa Demo en Monterrey."},
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
async def test_etapa2_equipo_completo_sin_gaps():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-2",
                json={"team": BASE_TEAM},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["team_count"] == 5
    assert data["next_stage"] == 3
    assert 2 in data["completed_stages"]
    assert data["inferences"]["functional_gaps"] == []
    assert data["inferences"]["continuity_risk"] is True  # solo 1 decisor


@pytest.mark.asyncio
async def test_etapa2_detecta_gap_finanzas():
    team_sin_cfo = [m for m in BASE_TEAM if m["role"] != "cfo"]
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-2",
                json={"team": team_sin_cfo},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    inferences = response.json()["inferences"]
    assert "finance" in inferences["functional_gaps"]
    assert any("finanzas" in a.lower() or "cfo" in a.lower() for a in inferences["alerts"])


@pytest.mark.asyncio
async def test_etapa2_concentracion_familiar_genera_alerta():
    team_familiar = [
        {"name": "Padre", "role": "ceo", "is_family": True, "makes_key_decisions": True},
        {"name": "Hijo",  "role": "cfo", "is_family": True, "makes_key_decisions": False},
        {"name": "Hija",  "role": "operations", "is_family": True, "makes_key_decisions": False},
        {"name": "Externo", "role": "commercial", "is_family": False, "makes_key_decisions": False},
    ]
    session = _mock_session(is_family_business=True)
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-2",
                json={"team": team_familiar},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    inferences = response.json()["inferences"]
    assert inferences["family_concentration"] == 75.0
    assert any("familia" in a.lower() for a in inferences["alerts"])


@pytest.mark.asyncio
async def test_etapa2_sin_etapa1_falla_400():
    session = _mock_session(completed_stages=[])  # etapa 1 no completada
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-2",
                json={"team": BASE_TEAM},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "Etapa 1" in response.json()["detail"]


@pytest.mark.asyncio
async def test_etapa2_equipo_vacio_falla_422():
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-2",
                json={"team": []},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_etapa2_memory_buffer_actualizado():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-2",
                json={"team": BASE_TEAM},
            )
    finally:
        app.dependency_overrides.clear()

    assert len(session.memory_buffer["team"]) == 5
    assert session.memory_buffer["team_inferences"]["centralization_level"] == "high"
    assert 2 in session.completed_stages
    # La narrativa se enriqueció con info del equipo
    assert "Equipo directivo" in session.memory_buffer["ai_context"]["company_narrative"]
