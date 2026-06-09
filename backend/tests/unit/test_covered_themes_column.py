from app.models import Base
from app.models.annual_plan import MonthlyPlan


def test_monthly_plan_has_covered_themes_column():
    cols = set(Base.metadata.tables["monthly_plans"].columns.keys())
    assert "covered_themes" in cols


def test_monthly_plan_instantiable_with_covered_themes():
    m = MonthlyPlan(month_index=1, period_year=2026, period_month=1, covered_themes=["fin"])
    assert m.covered_themes == ["fin"]
