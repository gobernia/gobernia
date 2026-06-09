from app.models.annual_plan import MonthlyPlan


def test_monthlyplan_tiene_minuta():
    m = MonthlyPlan(minuta={"carta": "x", "temas": []})
    assert m.minuta == {"carta": "x", "temas": []}


def test_minuta_default_none():
    m = MonthlyPlan()
    assert m.minuta is None
