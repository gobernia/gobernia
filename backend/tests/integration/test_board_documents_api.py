"""
Tests de integración del board pack de la sesión de consejo:
subir / listar / borrar documentos, y ruteo de documentos por rol en /analyse.
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user_id, get_db
from app.main import app

MOCK_USER_ID = "user_board_docs"
OTHER_USER_ID = "user_intruso"
MOCK_ONBOARDING_ID = uuid.uuid4()
MOCK_BOARD_ID = uuid.uuid4()

BUFFER = {
    "company": {"industry": "manufacturing"},
    "ai_context": {"company_narrative": "Empresa Demo."},
    "agent_configs": {},
}


def _board_session(user_id=MOCK_USER_ID):
    bs = MagicMock()
    bs.id = MOCK_BOARD_ID
    bs.onboarding_session_id = MOCK_ONBOARDING_ID
    bs.user_id = user_id
    bs.period_year = 2026
    bs.period_month = 6
    bs.status = "active"
    bs.kpi_snapshot = None
    bs.agent_analyses = None
    bs.agent_critiques = None
    bs.documents = []
    bs.messages = []
    bs.created_at = datetime.now(timezone.utc)
    return bs


def _document(filename="estado.pdf", document_type="financial", doc_id=None):
    return SimpleNamespace(
        id=doc_id or uuid.uuid4(),
        filename=filename,
        document_type=document_type,
        s3_key=f"documents/{MOCK_BOARD_ID}/{filename}",
        board_session_id=MOCK_BOARD_ID,
        created_at=datetime.now(timezone.utc),
    )


def _db_override(board_session=None, documents=None, document=None, added=None):
    async def override():
        db = AsyncMock()

        async def execute_se(query, *args, **kwargs):
            q = str(query)
            result = MagicMock()
            if "FROM documents" in q:
                result.scalar_one_or_none.return_value = document
                result.scalars.return_value.all.return_value = list(documents or [])
            elif "onboarding_sessions" in q:
                onb = MagicMock()
                onb.id = MOCK_ONBOARDING_ID
                onb.memory_buffer = BUFFER
                result.scalar_one_or_none.return_value = onb
                result.scalars.return_value.first.return_value = onb
                result.scalars.return_value.all.return_value = []
            else:  # board_sessions
                result.scalar_one_or_none.return_value = board_session
                result.scalars.return_value.all.return_value = []
            return result

        db.execute = AsyncMock(side_effect=execute_se)

        def add(obj):
            if added is not None:
                added.append(obj)
        db.add = MagicMock(side_effect=add)
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.delete = AsyncMock()
        db.close = AsyncMock()
        yield db

    return override


async def _user_override():
    return MOCK_USER_ID


# ── POST /board-sessions/{id}/documents ───────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_board_document_ok():
    added: list = []
    app.dependency_overrides[get_db] = _db_override(_board_session(), added=added)
    app.dependency_overrides[get_current_user_id] = _user_override

    with patch("app.api.v1.board_sessions.documents.upload_to_storage", new=AsyncMock(return_value="k")):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    f"/api/v1/board-sessions/{MOCK_BOARD_ID}/documents",
                    files={"file": ("estado.pdf", b"%PDF-1.4 fake", "application/pdf")},
                    data={"document_type": "financial"},
                )
        finally:
            app.dependency_overrides.clear()

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["filename"] == "estado.pdf"
    assert body["document_type"] == "financial"
    assert body["document_type_label"] == "Estados financieros"

    # La fila se creó con board_session_id (y con el onboarding del usuario)
    doc = added[0]
    assert doc.board_session_id == MOCK_BOARD_ID
    assert doc.session_id == MOCK_ONBOARDING_ID
    assert doc.user_id == MOCK_USER_ID


@pytest.mark.asyncio
async def test_upload_extension_no_permitida_400():
    app.dependency_overrides[get_db] = _db_override(_board_session())
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/v1/board-sessions/{MOCK_BOARD_ID}/documents",
                files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
                data={"document_type": "financial"},
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400
    assert "no permitido" in r.json()["detail"]


@pytest.mark.asyncio
async def test_upload_tipo_de_documento_invalido_400():
    app.dependency_overrides[get_db] = _db_override(_board_session())
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/v1/board-sessions/{MOCK_BOARD_ID}/documents",
                files={"file": ("estado.pdf", b"%PDF", "application/pdf")},
                data={"document_type": "no_existe"},
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400
    assert "Tipo de documento no válido" in r.json()["detail"]


@pytest.mark.asyncio
async def test_upload_archivo_muy_grande_400():
    app.dependency_overrides[get_db] = _db_override(_board_session())
    app.dependency_overrides[get_current_user_id] = _user_override
    big = b"x" * (10 * 1024 * 1024 + 1)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/v1/board-sessions/{MOCK_BOARD_ID}/documents",
                files={"file": ("grande.pdf", big, "application/pdf")},
                data={"document_type": "financial"},
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400
    assert "10 MB" in r.json()["detail"]


@pytest.mark.asyncio
async def test_upload_a_sesion_de_otro_usuario_403():
    app.dependency_overrides[get_db] = _db_override(_board_session(user_id=OTHER_USER_ID))
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/v1/board-sessions/{MOCK_BOARD_ID}/documents",
                files={"file": ("estado.pdf", b"%PDF", "application/pdf")},
                data={"document_type": "financial"},
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_upload_sesion_inexistente_404():
    app.dependency_overrides[get_db] = _db_override(None)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/v1/board-sessions/{uuid.uuid4()}/documents",
                files={"file": ("estado.pdf", b"%PDF", "application/pdf")},
                data={"document_type": "financial"},
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


# ── GET /board-sessions/{id}/documents ────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_board_documents_ok():
    docs = [_document(), _document("junta.pdf", "presentation")]
    app.dependency_overrides[get_db] = _db_override(_board_session(), documents=docs)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/api/v1/board-sessions/{MOCK_BOARD_ID}/documents")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["filename"] for i in items] == ["estado.pdf", "junta.pdf"]
    assert items[1]["document_type_label"] == "Presentación / material de la junta"


@pytest.mark.asyncio
async def test_list_documents_de_otro_usuario_403():
    app.dependency_overrides[get_db] = _db_override(_board_session(user_id=OTHER_USER_ID))
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/api/v1/board-sessions/{MOCK_BOARD_ID}/documents")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403


# ── DELETE /board-sessions/{id}/documents/{doc_id} ────────────────────────────

@pytest.mark.asyncio
async def test_delete_board_document_ok():
    doc = _document()
    app.dependency_overrides[get_db] = _db_override(_board_session(), document=doc)
    app.dependency_overrides[get_current_user_id] = _user_override

    with patch("app.api.v1.board_sessions.documents.delete_from_storage", return_value=True) as mock_del:
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.delete(
                    f"/api/v1/board-sessions/{MOCK_BOARD_ID}/documents/{doc.id}"
                )
        finally:
            app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["deleted"] is True
    mock_del.assert_called_once_with(doc.s3_key)


@pytest.mark.asyncio
async def test_delete_documento_inexistente_404():
    app.dependency_overrides[get_db] = _db_override(_board_session(), document=None)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete(
                f"/api/v1/board-sessions/{MOCK_BOARD_ID}/documents/{uuid.uuid4()}"
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_storage_falla_no_revienta():
    doc = _document()
    app.dependency_overrides[get_db] = _db_override(_board_session(), document=doc)
    app.dependency_overrides[get_current_user_id] = _user_override

    with patch("app.api.v1.board_sessions.documents.delete_from_storage", return_value=False):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.delete(
                    f"/api/v1/board-sessions/{MOCK_BOARD_ID}/documents/{doc.id}"
                )
        finally:
            app.dependency_overrides.clear()
    assert r.status_code == 200


# ── /analyse: ruteo de documentos por rol ─────────────────────────────────────

class _FakePersistSession:
    def __init__(self, refreshed):
        self._refreshed = refreshed

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, model, _id):
        return self._refreshed

    async def commit(self):
        return None


async def _analyse_capturando_documentos(documents):
    """Corre /analyse con los documentos dados y devuelve {agente: kwargs de run_agent_analysis}."""
    from app.models.board_session import BoardSession

    calls: dict = {}

    def fake_analysis(**kwargs):
        calls[kwargs["agent"]] = kwargs
        return {"summary": "ok", "findings": [], "alerts": [],
                "recommendations": [], "preguntas": []}

    app.dependency_overrides[get_db] = _db_override(_board_session(), documents=documents)
    app.dependency_overrides[get_current_user_id] = _user_override

    with patch("app.api.v1.board_sessions.router.run_agent_analysis", side_effect=fake_analysis), \
         patch("app.api.v1.board_sessions.router.run_challenger_critique", return_value={}), \
         patch("app.api.v1.board_sessions.router.run_agent_revision",
               side_effect=lambda **kw: kw["initial_analysis"]), \
         patch("app.api.v1.board_sessions.router.download_from_storage", return_value=b"%PDF fake"), \
         patch("app.db.session.AsyncSessionLocal", lambda: _FakePersistSession(BoardSession())):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    f"/api/v1/board-sessions/{MOCK_BOARD_ID}/analyse",
                    json={"agents": ["CFO", "CSO"]},
                )
        finally:
            app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    return calls, r.json()


@pytest.mark.asyncio
async def test_analyse_rutea_financial_al_cfo_y_no_al_cso():
    docs = [_document("estado.pdf", "financial")]
    calls, _ = await _analyse_capturando_documentos(docs)
    cfo_docs = calls["CFO"]["documents"]
    cso_docs = calls["CSO"]["documents"]
    assert [d["label"] for d in cfo_docs] and "estado.pdf" in cfo_docs[0]["label"]
    assert cfo_docs[0]["kind"] == "pdf"
    assert cso_docs == []


@pytest.mark.asyncio
async def test_analyse_rutea_presentation_al_cso_y_no_al_cfo():
    docs = [_document("junta.pdf", "presentation")]
    calls, _ = await _analyse_capturando_documentos(docs)
    assert calls["CFO"]["documents"] == []
    assert len(calls["CSO"]["documents"]) == 1
    assert "junta.pdf" in calls["CSO"]["documents"][0]["label"]


@pytest.mark.asyncio
async def test_analyse_xlsx_no_se_adjunta_pero_genera_nota():
    docs = [_document("cifras.xlsx", "financial")]
    calls, _ = await _analyse_capturando_documentos(docs)
    assert calls["CFO"]["documents"] == []
    assert "cifras.xlsx" in calls["CFO"]["documents_note"]
    assert "PDF" in calls["CFO"]["documents_note"]


@pytest.mark.asyncio
async def test_analyse_normaliza_analisis_legacy_en_la_respuesta():
    """Una sesión vieja (findings como list[str]) sale del API con el shape nuevo."""
    from app.models.board_session import BoardSession

    bs = _board_session()
    bs.agent_analyses = {"CRO": {"summary": "viejo", "findings": ["a", "b"], "alerts": ["x"]}}

    app.dependency_overrides[get_db] = _db_override(bs)
    app.dependency_overrides[get_current_user_id] = _user_override

    with patch("app.api.v1.board_sessions.router.run_agent_analysis",
               return_value={"summary": "s", "findings": [], "alerts": [],
                             "recommendations": [], "preguntas": []}), \
         patch("app.api.v1.board_sessions.router.run_challenger_critique", return_value={}), \
         patch("app.api.v1.board_sessions.router.run_agent_revision",
               side_effect=lambda **kw: kw["initial_analysis"]), \
         patch("app.db.session.AsyncSessionLocal", lambda: _FakePersistSession(BoardSession())):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    f"/api/v1/board-sessions/{MOCK_BOARD_ID}/analyse",
                    json={"agents": ["CFO"]},
                )
        finally:
            app.dependency_overrides.clear()

    assert r.status_code == 200
    cro = r.json()["analyses"]["CRO"]
    assert cro["findings"] == [{"texto": "a", "fuente": ""}, {"texto": "b", "fuente": ""}]
    assert cro["alerts"] == [{"nivel": "ambar", "texto": "x", "fuente": ""}]
