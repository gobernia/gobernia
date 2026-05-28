from datetime import date, datetime

from app.schemas.annual_plan import (
    AnnualPlanOut, AnnualPlanStatusOut, MonthlyPlanOut, ObjectiveOut,
    ObjectiveCreate, ObjectiveUpdate, AnnualTaskCreate,
)
from app.schemas.action_plan import ActionTaskOut


def test_action_task_out_plan_id_optional_and_new_fields():
    t = ActionTaskOut(
        id="t1", title="Hacer X", status="pendiente", priority="media",
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        objective_id="o1", kpi_ref="Margen EBITDA",
    )
    assert t.plan_id is None
    assert t.objective_id == "o1"
    assert t.kpi_ref == "Margen EBITDA"


def test_objective_out_nests_tasks():
    obj = ObjectiveOut(
        id="o1", title="Mejorar liquidez", description=None,
        kpi_refs=["Razón corriente"], order_index=0, tasks=[],
    )
    assert obj.kpi_refs == ["Razón corriente"]
    assert obj.tasks == []


def test_annual_plan_out_nests_months():
    plan = AnnualPlanOut(
        id="p1", title="Plan 12 meses", start_date=date.today(),
        status="active", diagnostico_summary="Resumen", genesis_session_id=None,
        months=[],
    )
    assert plan.status == "active"
    assert plan.months == []


def test_status_out():
    s = AnnualPlanStatusOut(status="generating", active_month_index=1)
    assert s.status == "generating"
    assert s.active_month_index == 1


def test_objective_and_task_create():
    oc = ObjectiveCreate(monthly_plan_id="m1", title="Nuevo objetivo")
    assert oc.kpi_refs == []
    tc = AnnualTaskCreate(objective_id="o1", title="Nueva tarea")
    assert tc.priority == "media"
    ou = ObjectiveUpdate(title="editado")
    assert ou.title == "editado"
