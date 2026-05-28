from datetime import date

from app.services.ai.annual_plan_generator import (
    month_calendar, compute_active_month_index, due_date_within_month,
)


def test_month_calendar_wraps_year():
    # start en nov 2026, month_index 1 = nov 2026, 3 = ene 2027
    assert month_calendar(2026, 11, 1) == (2026, 11)
    assert month_calendar(2026, 11, 2) == (2026, 12)
    assert month_calendar(2026, 11, 3) == (2027, 1)
    assert month_calendar(2026, 11, 12) == (2027, 10)


def test_compute_active_month_index():
    start = date(2026, 5, 1)
    assert compute_active_month_index(start, date(2026, 5, 15)) == 1
    assert compute_active_month_index(start, date(2026, 7, 2)) == 3
    # antes del inicio → 1; pasado el mes 12 → 12 (cap)
    assert compute_active_month_index(start, date(2026, 4, 1)) == 1
    assert compute_active_month_index(start, date(2030, 1, 1)) == 12


def test_due_date_within_month_clamps_day():
    assert due_date_within_month(2026, 2, 31) == date(2026, 2, 28)   # feb no bisiesto
    assert due_date_within_month(2026, 6, 15) == date(2026, 6, 15)
    assert due_date_within_month(2026, 6, 0) == date(2026, 6, 1)     # piso 1
