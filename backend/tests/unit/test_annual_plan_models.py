"""Verifica la definición de los modelos del plan de 12 meses."""
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.action_plan import ActionTask


def test_tablenames():
    assert AnnualPlan.__tablename__ == "annual_plans"
    assert MonthlyPlan.__tablename__ == "monthly_plans"
    assert Objective.__tablename__ == "objectives"


def test_action_task_has_new_columns():
    cols = ActionTask.__table__.columns
    assert "objective_id" in cols
    assert "kpi_ref" in cols
    # objective_id debe ser nullable (coexiste con plan_id legacy)
    assert cols["objective_id"].nullable is True
    assert cols["plan_id"].nullable is True


def test_monthly_plan_has_review_column():
    cols = MonthlyPlan.__table__.columns
    assert "review" in cols          # reservado para subproyecto E
    assert "month_index" in cols
    assert "period_year" in cols
    assert "period_month" in cols


def test_models_registered_in_metadata():
    from app.models import Base
    names = set(Base.metadata.tables.keys())
    assert {"annual_plans", "monthly_plans", "objectives"}.issubset(names)
