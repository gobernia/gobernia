"""
Tests de integración de Etapa 1.
Verifican que el endpoint guarda correctamente en el Memory Buffer
y que los condicionales se reflejan en la respuesta.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_123"
MOCK_SESSION_ID = str(uuid.uuid4())

BASE_PAYLOAD = {
    "company_name": "Empresa Demo S.A.",
    "industry": "manufacturing",
    "location_city": "Monterrey",
    "location_state": "Nuevo León",
    "location_country": "México",
    "years_operating": "10-25",
    "employees": "51-200",
    "annual_revenue": "5M-15M",
    "branches": "single",
    "is_family_business": False,
    "has_board": "yes",
}


def _mock_session(session_id=MOCK_SESSION_ID):
    session = MagicMock()
    session.id = uuid.UUID(session_id)
    session.user_id = MOCK_USER_ID
    session.completed_stages = []
    session.memory_buffer = {
        "session_id": session_id,
        "user_id": MOCK_USER_ID,
        "completed_stages": [],
        "team": [],
        "priorities": [],
        "diagnostic_responses": [],
        "documents": [],
        "onboarding_started_at": datetime.now(timezone.utc).isoformat(),
    }
    return session


def _make_db_override(session_id=MOCK_SESSION_ID):
    mock_session = _mock_session(session_id)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_session

    async def override_get_db():
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        yield mock_db

    return override_get_db


def _make_db_override_not_found():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    async def override_get_db():
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        yield mock_db

    return override_get_db


async def _override_user_id():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_etapa1_empresa_no_familiar():
    app.dependency_overrides[get_db] = _make_db_override()
    app.dependency_overrides[get_current_user_id] = _override_user_id

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-1",
                json=BASE_PAYLOAD,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["next_stage"] == 2
    assert 1 in data["completed_stages"]
    assert data["activated_modules"] == []
    assert "Empresa Demo" in data["summary"]


@pytest.mark.asyncio
async def test_etapa1_empresa_familiar_activa_modulo():
    app.dependency_overrides[get_db] = _make_db_override()
    app.dependency_overrides[get_current_user_id] = _override_user_id

    payload = {**BASE_PAYLOAD, "is_family_business": True,
               "family_generation": "2nd", "has_family_protocol": False}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-1", json=payload,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "family" in response.json()["activated_modules"]


@pytest.mark.asyncio
async def test_etapa1_6_sucursales_activa_multi_site():
    app.dependency_overrides[get_db] = _make_db_override()
    app.dependency_overrides[get_current_user_id] = _override_user_id

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-1",
                json={**BASE_PAYLOAD, "branches": "6+"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "multi_site" in response.json()["activated_modules"]


@pytest.mark.asyncio
async def test_etapa1_ingresos_altos_activa_advanced_metrics():
    app.dependency_overrides[get_db] = _make_db_override()
    app.dependency_overrides[get_current_user_id] = _override_user_id

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-1",
                json={**BASE_PAYLOAD, "annual_revenue": "15M+"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "advanced_metrics" in response.json()["activated_modules"]


@pytest.mark.asyncio
async def test_etapa1_familia_sin_generacion_falla_422():
    app.dependency_overrides[get_current_user_id] = _override_user_id
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-1",
                json={**BASE_PAYLOAD, "is_family_business": True},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_etapa1_session_no_encontrada_404():
    app.dependency_overrides[get_db] = _make_db_override_not_found()
    app.dependency_overrides[get_current_user_id] = _override_user_id

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-1",
                json=BASE_PAYLOAD,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_etapa1_memory_buffer_contiene_datos_empresa():
    """Verifica que el Memory Buffer se actualiza con los datos correctos."""
    mock_session = _mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_session

    async def override_get_db():
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = _override_user_id

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-1",
                json=BASE_PAYLOAD,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    # El memory buffer del mock debe haberse actualizado con los datos de la empresa
    buffer = mock_session.memory_buffer
    assert buffer["company"]["name"] == "Empresa Demo S.A."
    assert buffer["company"]["industry"] == "manufacturing"
    assert buffer["company"]["location"]["city"] == "Monterrey"
    assert buffer["ai_context"]["company_narrative"] != ""
    assert 1 in mock_session.completed_stages
