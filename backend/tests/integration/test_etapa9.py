"""
Tests de integración de Etapa 9 — BoardSession y chat con agentes.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_board"
MOCK_ONBOARDING_ID = str(uuid.uuid4())
MOCK_BOARD_ID = str(uuid.uuid4())

FULL_BUFFER = {
    "company": {"industry": "manufacturing", "employees": "11-50", "annual_revenue": "1M-5M"},
    "ai_context": {"company_narrative": "Empresa Demo. Diagnóstico completo."},
    "vision": {"statement": "Ser líderes en 5 años."},
    "governance": {"score": 80.0, "level": "Consolidado"},
    "agent_configs": {
        "CFO":     {"tone": "formal",        "alert_sensitivity": "high"},
        "CSO":     {"tone": "strategic",     "alert_sensitivity": "medium"},
        "CRO":     {"tone": "direct",        "alert_sensitivity": "high"},
        "Auditor": {"tone": "collaborative", "alert_sensitivity": "medium"},
    },
    "documents": [],
}


def _mock_onboarding(completed_stages=None):
    s = MagicMock()
    s.id = uuid.UUID(MOCK_ONBOARDING_ID)
    s.user_id = MOCK_USER_ID
    s.completed_stages = completed_stages if completed_stages is not None else list(range(1, 9))
    s.memory_buffer = FULL_BUFFER
    s.governance_score = 80.0
    return s


def _mock_board_session(status="draft", kpi_snapshot=None, agent_analyses=None, messages=None):
    bs = MagicMock()
    bs.id = uuid.UUID(MOCK_BOARD_ID)
    bs.onboarding_session_id = uuid.UUID(MOCK_ONBOARDING_ID)
    bs.user_id = MOCK_USER_ID
    bs.period_year = 2025
    bs.period_month = 4
    bs.status = status
    bs.kpi_snapshot = kpi_snapshot
    bs.agent_analyses = agent_analyses
    bs.governance_score_snapshot = 80.0
    bs.profile_snapshot = FULL_BUFFER
    bs.documents = []
    bs.messages = messages or []
    bs.created_at = datetime.now(timezone.utc)
    bs.completed_at = None
    return bs


def _db_override_onboarding(onboarding, board_session=None, no_existing=True):
    """
    Mock de DB para queries de onboarding y board sessions.
    """
    async def override():
        db = AsyncMock()

        call_count = 0

        async def execute_side_effect(query, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            query_str = str(query)

            if "onboarding_sessions" in query_str:
                result.scalars.return_value.first.return_value = onboarding
                result.scalar_one_or_none.return_value = onboarding
            elif "board_sessions" in query_str:
                if no_existing:
                    result.scalar_one_or_none.return_value = None
                else:
                    result.scalar_one_or_none.return_value = board_session
                result.scalars.return_value.all.return_value = [board_session] if board_session else []
            else:
                result.scalar_one_or_none.return_value = None
                result.scalars.return_value.all.return_value = []

            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        yield db

    return override


async def _user_override():
    return MOCK_USER_ID


# ── POST /board-sessions ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_board_session_ok():
    onboarding = _mock_onboarding()
    app.dependency_overrides[get_db] = _db_override_onboarding(onboarding)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/board-sessions",
                json={"period_year": 2025, "period_month": 4},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["period_year"] == 2025
    assert data["period_month"] == 4
    assert data["period_label"] == "Abril 2025"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_create_board_session_sin_onboarding_completo_falla_400():
    onboarding = _mock_onboarding(completed_stages=[1, 2, 3])
    app.dependency_overrides[get_db] = _db_override_onboarding(onboarding)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/board-sessions",
                json={"period_year": 2025, "period_month": 4},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_board_session_duplicado_falla_409():
    onboarding = _mock_onboarding()
    existing_bs = _mock_board_session()
    app.dependency_overrides[get_db] = _db_override_onboarding(onboarding, existing_bs, no_existing=False)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/board-sessions",
                json={"period_year": 2025, "period_month": 4},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


# ── GET /board-sessions ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_board_sessions_ok():
    onboarding = _mock_onboarding()
    bs = _mock_board_session()
    app.dependency_overrides[get_db] = _db_override_onboarding(onboarding, bs, no_existing=False)
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/board-sessions")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── POST /board-sessions/{id}/analyse ────────────────────────────────────────

class _FakePersistSession:
    """
    Sesión falsa para el bloque de persistencia de /analyse, que abre su propia
    AsyncSessionLocal() (separada de la inyectada por get_db) para guardar los
    análisis tras liberar la conexión durante las llamadas a Claude.
    """
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


@pytest.mark.asyncio
async def test_analyse_sin_api_key_devuelve_placeholder():
    onboarding = _mock_onboarding()
    bs = _mock_board_session(status="active")

    async def override():
        db = AsyncMock()
        async def execute_se(query, *args, **kwargs):
            result = MagicMock()
            query_str = str(query)
            if "onboarding_sessions" in query_str:
                result.scalar_one_or_none.return_value = onboarding
                result.scalars.return_value.first.return_value = onboarding
            elif "board_sessions" in query_str:
                result.scalar_one_or_none.return_value = bs
                result.scalars.return_value.all.return_value = []
            else:
                result.scalar_one_or_none.return_value = None
                result.scalars.return_value.all.return_value = []
            return result
        db.execute = AsyncMock(side_effect=execute_se)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override
    app.dependency_overrides[get_current_user_id] = _user_override

    # El endpoint reabre una AsyncSessionLocal() propia para persistir; la mockeamos
    # con una BoardSession transitoria para no golpear la DB real ni dar 404 al persistir.
    from app.models.board_session import BoardSession
    refreshed = BoardSession()

    with patch("app.services.ai.agents.base.settings") as mock_s, \
         patch("app.db.session.AsyncSessionLocal", lambda: _FakePersistSession(refreshed)):
        mock_s.ANTHROPIC_API_KEY = ""
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/board-sessions/{MOCK_BOARD_ID}/analyse",
                    json={"agents": ["CFO", "Auditor"]},
                )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert "CFO" in data["analyses"]
    assert "Auditor" in data["analyses"]
    assert "summary" in data["analyses"]["CFO"]


@pytest.mark.asyncio
async def test_analyse_agente_invalido_falla_400():
    onboarding = _mock_onboarding()
    bs = _mock_board_session()

    async def override():
        db = AsyncMock()
        async def execute_se(query, *args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = bs
            result.scalars.return_value.first.return_value = onboarding
            result.scalars.return_value.all.return_value = []
            return result
        db.execute = AsyncMock(side_effect=execute_se)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override
    app.dependency_overrides[get_current_user_id] = _user_override

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/board-sessions/{MOCK_BOARD_ID}/analyse",
                json={"agents": ["CEO"]},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


# ── POST /board-sessions/{id}/chat ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_sin_api_key_devuelve_respuesta():
    onboarding = _mock_onboarding()
    bs = _mock_board_session()

    async def override():
        db = AsyncMock()
        async def execute_se(query, *args, **kwargs):
            result = MagicMock()
            query_str = str(query)
            if "onboarding_sessions" in query_str:
                result.scalar_one_or_none.return_value = onboarding
            else:
                result.scalar_one_or_none.return_value = bs
            return result
        db.execute = AsyncMock(side_effect=execute_se)
        agent_msg = MagicMock()
        agent_msg.id = uuid.uuid4()
        agent_msg.role = "assistant"
        agent_msg.agent = "CFO"
        agent_msg.content = "[CFO Agent] placeholder"
        agent_msg.created_at = datetime.now(timezone.utc)

        def add_side_effect(obj):
            if hasattr(obj, 'role') and obj.role == "assistant":
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now(timezone.utc)
        db.add = MagicMock(side_effect=add_side_effect)
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override
    app.dependency_overrides[get_current_user_id] = _user_override

    with patch("app.services.ai.agents.base.settings") as mock_s:
        mock_s.ANTHROPIC_API_KEY = ""
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/board-sessions/{MOCK_BOARD_ID}/chat",
                    json={"content": "¿Cómo está el margen operativo?", "agent": "CFO"},
                )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert data["agent"] == "CFO"
    assert len(data["content"]) > 0
