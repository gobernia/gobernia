from app.models.annual_plan import MonthlyPlan


def test_monthlyplan_tiene_chair_agenda():
    m = MonthlyPlan(chair_agenda={"carta": "x", "items": []})
    assert m.chair_agenda == {"carta": "x", "items": []}


def test_chair_agenda_default_none():
    m = MonthlyPlan()
    assert m.chair_agenda is None
