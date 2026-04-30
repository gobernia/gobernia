"""
Tests de integración de Etapa 6 — GET items y POST governance score.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db
from app.services.ai.governance_engine import build_governance_items

MOCK_USER_ID = "user_test_gov"
MOCK_SESSION_ID = str(uuid.uuid4())

BASE_BUFFER = {
    "company": {"is_family_business": False},
}

FAMILY_BUFFER = {
    "company": {"is_family_business": True},
}


def _mock_session(completed_stages=None, buffer=None):
    session = MagicMock()
    session.id = uuid.UUID(MOCK_SESSION_ID)
    session.user_id = MOCK_USER_ID
    session.completed_stages = completed_stages if completed_stages is not None else [1, 2, 3, 4, 5]
    session.memory_buffer = buffer or BASE_BUFFER
    session.governance_score = None
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


def _all_yes_inputs(buffer=None):
    buf = buffer or BASE_BUFFER
    items = build_governance_items(buf)
    return [{"key": i.key, "response": "yes"} for i in items]


# ── GET /etapa-6/items ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_items_no_familiar():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-6/items")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total_items"] == 10
    assert data["includes_family"] is False
    assert not any(i["is_conditional"] for i in data["items"])


@pytest.mark.asyncio
async def test_get_items_familiar_incluye_protocolo():
    session = _mock_session(buffer=FAMILY_BUFFER)
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-6/items")
    finally:
        app.dependency_overrides.clear()

    data = response.json()
    assert data["total_items"] == 13
    assert data["includes_family"] is True
    keys = {i["key"] for i in data["items"]}
    assert "has_family_protocol" in keys


@pytest.mark.asyncio
async def test_get_items_sin_etapa5_falla_400():
    session = _mock_session(completed_stages=[1, 2, 3, 4])
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-6/items")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


# ── POST /etapa-6 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_etapa6_todos_yes_score_100():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-6",
                json={"items": _all_yes_inputs()},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["governance_score"] == 100.0
    assert data["governance_level"] == "Excelente"
    assert data["next_stage"] == 7
    assert 6 in data["completed_stages"]
    assert data["gaps"] == []


@pytest.mark.asyncio
async def test_submit_etapa6_todos_no_score_0():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    items = build_governance_items(BASE_BUFFER)
    all_no = [{"key": i.key, "response": "no"} for i in items]

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-6",
                json={"items": all_no},
            )
    finally:
        app.dependency_overrides.clear()

    data = response.json()
    assert data["governance_score"] == 0.0
    assert data["governance_level"] == "Inicial"
    assert len(data["gaps"]) == 10
    assert len(data["recommendations"]) > 0


@pytest.mark.asyncio
async def test_submit_etapa6_guarda_governance_score_en_sesion():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-6",
                json={"items": _all_yes_inputs()},
            )
    finally:
        app.dependency_overrides.clear()

    assert session.governance_score == 100.0
    assert "governance" in session.memory_buffer


@pytest.mark.asyncio
async def test_submit_etapa6_sin_etapa5_falla_400():
    session = _mock_session(completed_stages=[1, 2, 3, 4])
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-6",
                json={"items": _all_yes_inputs()},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_submit_etapa6_dimension_scores_en_respuesta():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-6",
                json={"items": _all_yes_inputs()},
            )
    finally:
        app.dependency_overrides.clear()

    data = response.json()
    dims = {d["dimension"] for d in data["dimension_scores"]}
    assert "board" in dims
    assert "compliance" in dims
    assert "documentation" in dims
