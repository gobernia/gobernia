from app.models.annual_plan import AnnualPlan
from app.models.action_plan import ActionTask


def test_annual_plan_tiene_horizon_y_milestones():
    cols = AnnualPlan.__table__.columns.keys()
    assert "horizon_years" in cols
    assert "milestones" in cols


def test_action_task_tiene_required_doc():
    assert "required_doc" in ActionTask.__table__.columns.keys()


def test_horizon_default_3():
    assert AnnualPlan.__table__.columns["horizon_years"].default.arg == 3
