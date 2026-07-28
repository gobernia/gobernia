"""Acta HISTÓRICA por sesión de consejo — foto inmutable congelada al primer descargue.

GET /board-sessions/{id}/acta/pdf:
  - 1er llamado con acta_snapshot None → CONGELA (arma la cadena desde el plan activo)
    y devuelve el PDF.
  - 2º llamado → reutiliza bs.acta_snapshot, NO recomputa (no toca el plan ni build_orden_cadena).

Tests con mocks (mismo patrón que test_orden_cadena_api).
"""
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_current_user_id, get_db


def _user():
    return "user-123"


def _db_override(db):
    async def _dep():
        yield db
    return _dep


def _pilar_aprobado(indice, nombre):
    return {
        "indice": indice, "nombre": nombre, "descripcion": f"desc {nombre}",
        "objetivo": f"obj {nombre}", "kpis": [{"label": f"kpi {nombre}", "meta": ""}],
        "estrategias": [f"estrategia {nombre}"],
    }


def _plan(plan_anual=None):
    p = MagicMock()
    p.id = "plan-1"
    p.plan_anual = plan_anual
    return p


def _task(required_doc, status="pendiente", due_date=None, id=None):
    t = MagicMock()
    t.required_doc = required_doc
    t.status = status
    t.due_date = due_date
    if id is not None:
        t.id = id
    return t


def _board_session(acta_snapshot=None):
    bs = MagicMock()
    bs.id = uuid.uuid4()
    bs.user_id = "user-123"
    bs.period_year = 2026
    bs.period_month = 3
    bs.completed_at = None
    bs.acta_snapshot = acta_snapshot
    return bs


def _db_freeze(bs, plan, task_rows=None, evidence_rows=None, compromiso_rows=None,
               company_name=None, logo_row=None):
    """Secuencia de execute del PRIMER descargue (acta_snapshot None):
    #1 _get_board_session_or_404 (scalar_one_or_none → bs)
    #2 plan activo (scalar_one_or_none → plan)
    #3 build_orden_cadena: tareas (.all())
    #4 evidencia (.all(), solo si hay tareas con pilar_index)
    #5 compromisos (.scalars().all())
    #6 OnboardingSession (scalar_one_or_none → onb con company)
    #7 CompanyLogo (scalar_one_or_none → logo)
    """
    bs_res = MagicMock()
    bs_res.scalar_one_or_none.return_value = bs
    plan_res = MagicMock()
    plan_res.scalar_one_or_none.return_value = plan
    tasks_res = MagicMock()
    tasks_res.all.return_value = task_rows or []
    ev_res = MagicMock()
    ev_res.all.return_value = evidence_rows or []
    comp_res = MagicMock()
    comp_res.scalars.return_value.all.return_value = compromiso_rows or []
    onb = MagicMock()
    onb.memory_buffer = {"company": {"name": company_name}} if company_name else {}
    onb_res = MagicMock()
    onb_res.scalar_one_or_none.return_value = onb
    logo_res = MagicMock()
    logo_res.scalar_one_or_none.return_value = logo_row
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[bs_res, plan_res, tasks_res, ev_res, comp_res, onb_res, logo_res]
    )
    db.commit = AsyncMock()
    return db


def _db_reuse(bs, company_name=None, logo_row=None):
    """Secuencia del 2º descargue (acta_snapshot YA existe): solo branding.
    #1 _get_board_session_or_404  #2 OnboardingSession  #3 CompanyLogo."""
    bs_res = MagicMock()
    bs_res.scalar_one_or_none.return_value = bs
    onb = MagicMock()
    onb.memory_buffer = {"company": {"name": company_name}} if company_name else {}
    onb_res = MagicMock()
    onb_res.scalar_one_or_none.return_value = onb
    logo_res = MagicMock()
    logo_res.scalar_one_or_none.return_value = logo_row
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[bs_res, onb_res, logo_res])
    db.commit = AsyncMock()
    return db


async def _call(db, session_id):
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.get(f"/api/v1/board-sessions/{session_id}/acta/pdf")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_acta_por_sesion_congela_y_devuelve_pdf():
    bs = _board_session(acta_snapshot=None)
    plan = _plan(plan_anual={
        "anio": 2026, "aprobado": True, "aprobado_at": "2026-01-01T00:00:00+00:00",
        "pilares": [_pilar_aprobado(0, "Salud Financiera"), _pilar_aprobado(1, "B")],
    })
    rows = [(_task("Contrato", status="completada", id="t1"), 0)]

    r = await _call(_db_freeze(bs, plan, rows, [], [], company_name="ACME"), bs.id)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"

    # Se congeló: acta_snapshot quedó poblado con el periodo de LA SESIÓN.
    assert bs.acta_snapshot is not None
    assert bs.acta_snapshot["periodo_label"] == "Marzo 2026"
    assert bs.acta_snapshot["cadena"]["aprobado"] is True


@pytest.mark.asyncio
async def test_segundo_descargue_reutiliza_snapshot_sin_recomputar():
    # Acta ya congelada de una sesión previa (foto inmutable).
    snapshot = {
        "cadena": {"aprobado": True, "anio": 2026, "puntos": []},
        "periodo_label": "Marzo 2026",
        "fecha_iso": "2026-03-31",
        "generated_at": "2026-03-31T12:00:00+00:00",
    }
    bs = _board_session(acta_snapshot=snapshot)

    db = _db_reuse(bs, company_name="ACME")
    r = await _call(db, bs.id)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"

    # NO recomputó: solo las 3 queries de branding (sin plan ni build_orden_cadena),
    # y el snapshot quedó intacto (mismo generated_at).
    assert db.execute.call_count == 3
    assert db.commit.await_count == 0
    assert bs.acta_snapshot["generated_at"] == "2026-03-31T12:00:00+00:00"


@pytest.mark.asyncio
async def test_sin_plan_activo_404():
    bs = _board_session(acta_snapshot=None)
    bs_res = MagicMock()
    bs_res.scalar_one_or_none.return_value = bs
    plan_res = MagicMock()
    plan_res.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[bs_res, plan_res])
    db.commit = AsyncMock()
    r = await _call(db, bs.id)
    assert r.status_code == 404
