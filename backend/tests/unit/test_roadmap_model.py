from app.models.annual_plan import AnnualPlan


def test_annual_plan_tiene_columna_roadmap():
    assert "roadmap" in AnnualPlan.__table__.columns
    assert AnnualPlan.__table__.columns["roadmap"].nullable is True
