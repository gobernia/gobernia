"""
Tests de integración de Etapa 4 — endpoints GET questions y POST respuestas.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db
from app.services.ai.question_engine import build_question_set

MOCK_USER_ID = "user_test_123"
MOCK_SESSION_ID = str(uuid.uuid4())

BASE_BUFFER = {
    "company": {"is_family_business": False},
    "priorities": [
        {"challenge": "profitability",    "rank": 1, "activated_areas": ["finance"]},
        {"challenge": "commercial_growth","rank": 2, "activated_areas": ["commercial"]},
        {"challenge": "talent",           "rank": 3, "activated_areas": ["hr"]},
    ],
    "ai_context": {"company_narrative": "Empresa Demo. Equipo. Prioridades."},
    "onboarding_started_at": datetime.now(timezone.utc).isoformat(),
}


def _mock_session(completed_stages=None, buffer=None):
    session = MagicMock()
    session.id = uuid.UUID(MOCK_SESSION_ID)
    session.user_id = MOCK_USER_ID
    session.completed_stages = completed_stages if completed_stages is not None else [1, 2, 3]
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


def _all_yes_responses(buffer=None):
    questions = build_question_set(buffer or BASE_BUFFER)
    return [{"question_id": q.question_id, "response": "yes"} for q in questions]


@pytest.mark.asyncio
async def test_get_questions_retorna_set_personalizado():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-4/questions")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total_questions"] > 7  # más que solo las base
    assert data["total_questions"] == len(data["questions"])


@pytest.mark.asyncio
async def test_submit_etapa4_genera_matrices():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-4",
                json={"responses": _all_yes_responses()},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["next_stage"] == 5
    assert 4 in data["completed_stages"]
    assert "business_summary" in data["matrices"]
    assert data["matrices"]["strength_count"] > 0


@pytest.mark.asyncio
async def test_etapa4_empresa_fortalecida_todos_yes():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-4",
                json={"responses": _all_yes_responses()},
            )
    finally:
        app.dependency_overrides.clear()

    matrices = response.json()["matrices"]
    assert matrices["weakness_count"] == 0
    assert matrices["strength_count"] > 0


@pytest.mark.asyncio
async def test_etapa4_empresa_debil_todos_no():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    questions = build_question_set(BASE_BUFFER)
    all_no = [{"question_id": q.question_id, "response": "no"} for q in questions]

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-4",
                json={"responses": all_no},
            )
    finally:
        app.dependency_overrides.clear()

    matrices = response.json()["matrices"]
    assert matrices["strength_count"] == 0
    assert matrices["weakness_count"] > 0


@pytest.mark.asyncio
async def test_etapa4_sin_etapa3_falla_400():
    session = _mock_session(completed_stages=[1, 2])
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-4",
                json={"responses": _all_yes_responses()},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_etapa4_memory_buffer_contiene_matrices():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-4",
                json={"responses": _all_yes_responses()},
            )
    finally:
        app.dependency_overrides.clear()

    buf = session.memory_buffer
    assert "matrices" in buf
    assert "mefi" in buf["matrices"]
    assert "mefe" in buf["matrices"]
    assert "swot" in buf["matrices"]
    assert "Diagnóstico" in buf["ai_context"]["company_narrative"]
