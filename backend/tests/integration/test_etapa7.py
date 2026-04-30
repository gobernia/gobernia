"""
Tests de integración de Etapa 7 — upload de documentos y completado de etapa.
"""
import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_docs"
MOCK_SESSION_ID = str(uuid.uuid4())

BASE_BUFFER = {
    "company": {"industry": "manufacturing"},
    "documents": [],
}

BUFFER_WITH_DOC = {
    "company": {"industry": "manufacturing"},
    "documents": [
        {
            "document_id": str(uuid.uuid4()),
            "filename": "estados_financieros.pdf",
            "document_type": "financial",
            "file_size_kb": 150.5,
            "status": "pending",
        }
    ],
}


def _mock_session(completed_stages=None, buffer=None):
    session = MagicMock()
    session.id = uuid.UUID(MOCK_SESSION_ID)
    session.user_id = MOCK_USER_ID
    session.completed_stages = (
        completed_stages if completed_stages is not None else [1, 2, 3, 4, 5, 6]
    )
    session.memory_buffer = dict(buffer or BASE_BUFFER)
    return session


def _db_override(session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = session

    async def override():
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        yield db

    return override


async def _user_override():
    return MOCK_USER_ID


def _pdf_file(name="test.pdf", size_kb=100):
    content = b"%PDF-1.4 fake content " * (size_kb * 50)
    return ("file", (name, io.BytesIO(content), "application/pdf"))


# ── POST /etapa-7/upload ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_documento_ok():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    with patch("app.api.v1.onboarding.etapa7.upload_to_storage", new=AsyncMock(return_value="documents/key")):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-7/upload",
                    files=[_pdf_file()],
                    data={"document_type": "financial"},
                )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["document_type"] == "financial"
    assert data["document_type_label"] == "Estados financieros"
    assert "document_id" in data


@pytest.mark.asyncio
async def test_upload_actualiza_memory_buffer():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    with patch("app.api.v1.onboarding.etapa7.upload_to_storage", new=AsyncMock(return_value="k")):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await client.post(
                    f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-7/upload",
                    files=[_pdf_file()],
                    data={"document_type": "bylaws"},
                )
        finally:
            app.dependency_overrides.clear()

    docs = session.memory_buffer.get("documents", [])
    assert len(docs) == 1
    assert docs[0]["document_type"] == "bylaws"


@pytest.mark.asyncio
async def test_upload_extension_invalida_falla_400():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-7/upload",
                files=[("file", ("malware.exe", io.BytesIO(b"bad"), "application/octet-stream"))],
                data={"document_type": "other"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "permitido" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_sin_etapa6_falla_400():
    session = _mock_session(completed_stages=[1, 2, 3, 4, 5])
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-7/upload",
                files=[_pdf_file()],
                data={"document_type": "financial"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_archivo_demasiado_grande_falla_400():
    session = _mock_session()
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    # Crear archivo > 10MB
    big_content = b"x" * (11 * 1024 * 1024)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-7/upload",
                files=[("file", ("huge.pdf", io.BytesIO(big_content), "application/pdf"))],
                data={"document_type": "financial"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "10" in response.json()["detail"]


# ── POST /etapa-7/complete ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_con_documentos_ok():
    session = _mock_session(buffer=BUFFER_WITH_DOC)
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-7/complete"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["next_stage"] == 8
    assert 7 in data["completed_stages"]
    assert data["document_count"] == 1
    assert len(data["documents"]) == 1


@pytest.mark.asyncio
async def test_complete_sin_documentos_falla_400():
    session = _mock_session(buffer=BASE_BUFFER)
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-7/complete"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "documento" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_complete_sin_etapa6_falla_400():
    session = _mock_session(completed_stages=[1, 2, 3, 4, 5], buffer=BUFFER_WITH_DOC)
    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/onboarding/{MOCK_SESSION_ID}/etapa-7/complete"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
