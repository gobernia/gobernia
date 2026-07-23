"""
La VALIDACIÓN de evidencias al sesionar (`/board-sessions/{id}/analyse`).

Reglas que se prueban:
- Determinista: una tarea del periodo marcada `completada` con CERO evidencias → el Consejo la deja
  `insuficiente` SIN llamar a la IA, y esa validación se persiste en la tarea.
- Resiliencia: si la validación revienta, la sesión NO se cae — la deliberación y los acuerdos
  se guardan igual y el endpoint responde 200.
"""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.board_sessions.router as bs_router
from app.main import app
from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.core.dependencies import get_current_user_id, get_db
from tests.integration.test_etapa9 import (
    MOCK_BOARD_ID, MOCK_USER_ID, _mock_board_session, _mock_onboarding,
)


async def _user_override():
    return MOCK_USER_ID


def _plan_month_task(status="completada"):
    plan = AnnualPlan(id=uuid.uuid4(), user_id=MOCK_USER_ID, title="P",
                      start_date=date.today(), status="active")
    plan.horizon_years = 1
    plan.roadmap = None
    obj = Objective(id=uuid.uuid4(), monthly_plan_id=uuid.uuid4(), title="Obj", order_index=0)
    obj.kpi_refs = None
    month = MonthlyPlan(id=uuid.uuid4(), annual_plan_id=plan.id, month_index=1,
                        period_year=2026, period_month=1, status="active")
    month.objectives = [obj]
    task = ActionTask(id=uuid.uuid4(), plan_id=None, objective_id=obj.id,
                      title="Cerrar caja", status=status, priority="media", order_index=0)
    task.created_at = datetime.now(timezone.utc); task.updated_at = task.created_at
    task.validacion = None
    return plan, month, obj, task


class _FakePersist:
    """Sesión de persistencia falsa que devuelve la tarea cuando /analyse la busca por id."""
    def __init__(self, refreshed, task):
        self._refreshed = refreshed
        self._task = task

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, model, _id):
        return self._refreshed

    async def execute(self, stmt):
        rows = [self._task] if "action_tasks" in str(stmt) else []

        class _R:
            def scalars(self):
                return self

            def all(self):
                return rows
        return _R()

    def add(self, obj):
        pass

    async def refresh(self, _obj):
        return None

    async def commit(self):
        return None


def _db_override(onboarding, bs, plan, month, task):
    async def override():
        db = AsyncMock()

        async def execute_se(query, *a, **k):
            q = str(query)
            r = MagicMock()
            r.scalars.return_value.all.return_value = []
            r.scalars.return_value.first.return_value = None
            if "onboarding_sessions" in q:
                r.scalar_one_or_none.return_value = onboarding
                r.scalars.return_value.first.return_value = onboarding
            elif "board_sessions" in q:
                r.scalar_one_or_none.return_value = bs
            elif "annual_plans" in q:
                r.scalar_one_or_none.return_value = plan
            elif "monthly_plans" in q:
                r.scalars.return_value.all.return_value = [month]
            elif "action_tasks" in q:
                r.scalars.return_value.all.return_value = [task]
            elif "evidences" in q:
                r.scalars.return_value.all.return_value = []   # CERO evidencias
            else:
                r.scalar_one_or_none.return_value = None
            return r

        db.execute = AsyncMock(side_effect=execute_se)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.close = AsyncMock()
        yield db

    return override


_STUB_CONCLUSION = {"conclusion": "El Consejo concluye.", "avance_roadmap": "",
                    "riesgos": [], "acuerdos": []}


@pytest.mark.asyncio
async def test_completada_sin_evidencia_queda_insuficiente_y_se_persiste(monkeypatch):
    onboarding = _mock_onboarding()
    bs = _mock_board_session(status="active")
    plan, month, obj, task = _plan_month_task(status="completada")

    # Stub de la deliberación: hermético y rápido (no red).
    monkeypatch.setattr(bs_router, "run_deliberacion", lambda **k: dict(_STUB_CONCLUSION))

    from app.models.board_session import BoardSession
    refreshed = BoardSession()

    app.dependency_overrides[get_db] = _db_override(onboarding, bs, plan, month, task)
    app.dependency_overrides[get_current_user_id] = _user_override

    with patch("app.services.ai.agents.base.settings") as mock_s, \
         patch("app.db.session.AsyncSessionLocal", lambda: _FakePersist(refreshed, task)):
        mock_s.ANTHROPIC_API_KEY = ""
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    f"/api/v1/board-sessions/{MOCK_BOARD_ID}/analyse",
                    json={"agents": ["Auditor"]},
                )
        finally:
            app.dependency_overrides.clear()

    assert r.status_code == 200
    # El Consejo dejó la tarea insuficiente (marcada hecha sin ningún documento) SIN llamar a la IA.
    assert task.validacion is not None
    assert task.validacion["estado"] == "insuficiente"
    assert task.validacion["board_session_id"] == MOCK_BOARD_ID
    assert "validated_at" in task.validacion


@pytest.mark.asyncio
async def test_validacion_que_revienta_no_tumba_la_sesion(monkeypatch):
    onboarding = _mock_onboarding()
    bs = _mock_board_session(status="active")
    plan, month, obj, task = _plan_month_task(status="completada")

    from app.models.board_session import BoardSession
    refreshed = BoardSession()

    monkeypatch.setattr(bs_router, "run_deliberacion", lambda **k: dict(_STUB_CONCLUSION))

    async def _boom(*a, **k):
        raise RuntimeError("validación caída")

    monkeypatch.setattr(bs_router, "_validar_evidencias_del_periodo", _boom)

    app.dependency_overrides[get_db] = _db_override(onboarding, bs, plan, month, task)
    app.dependency_overrides[get_current_user_id] = _user_override

    with patch("app.services.ai.agents.base.settings") as mock_s, \
         patch("app.db.session.AsyncSessionLocal", lambda: _FakePersist(refreshed, task)):
        mock_s.ANTHROPIC_API_KEY = ""
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    f"/api/v1/board-sessions/{MOCK_BOARD_ID}/analyse",
                    json={"agents": ["Auditor"]},
                )
        finally:
            app.dependency_overrides.clear()

    # La sesión respondió pese al fallo de la validación; la tarea quedó sin validación.
    assert r.status_code == 200
    assert task.validacion is None
