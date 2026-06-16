from datetime import date
from app.services.ai.annual_plan_generator import compute_active_month_index


def test_cap_default_12():
    assert compute_active_month_index(date(2020, 1, 1), date(2030, 1, 1)) == 12


def test_cap_a_total_months():
    start = date(2026, 1, 1)
    assert compute_active_month_index(start, date(2027, 9, 1), total_months=36) == 21
    assert compute_active_month_index(start, date(2031, 1, 1), total_months=36) == 36


def test_minimo_1():
    assert compute_active_month_index(date(2026, 6, 1), date(2026, 1, 1), total_months=36) == 1
