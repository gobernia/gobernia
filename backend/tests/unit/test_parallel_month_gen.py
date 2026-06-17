"""
Tests para la generación paralela de quarters (_generate_all_quarters).
Migrado de _generate_all_month_tasks a la nueva orquestación trimestre-primero.
"""
import pytest

import app.tasks.annual_plan_tasks as t


@pytest.mark.asyncio
async def test_genera_4_quarters_por_anio(monkeypatch):
    """horizon=1 → 4 quarters, cada uno con 3 meses (12 total)."""
    calls = []

    def fake_gqp(memory_buffer, kpi_labels, milestones, year, quarter):
        base = (year - 1) * 12 + (quarter - 1) * 3
        calls.append((year, quarter))
        return [{"month_index": base + i, "focus": f"q{quarter}m{i}", "objectives": []}
                for i in range(1, 4)]

    monkeypatch.setattr(t, "generate_quarter_plan", fake_gqp)

    results = await t._generate_all_quarters({}, [], {"items": []}, horizon=1)

    # 4 quarters para horizon=1
    assert len(results) == 4
    # cada quarter devuelve 3 meses
    assert all(len(q) == 3 for q in results)
    # gather preserva el orden (Q1,Q2,Q3,Q4)
    assert results[0][0]["month_index"] == 1
    assert results[0][2]["month_index"] == 3
    assert results[3][0]["month_index"] == 10
    assert results[3][2]["month_index"] == 12
    # los 4 quarters fueron llamados
    assert len(calls) == 4
    assert sorted(calls) == [(1, 1), (1, 2), (1, 3), (1, 4)]


@pytest.mark.asyncio
async def test_genera_12_quarters_para_3_anios(monkeypatch):
    """horizon=3 → 12 quarters, 36 meses en total."""
    call_count = []

    def fake_gqp(memory_buffer, kpi_labels, milestones, year, quarter):
        call_count.append(1)
        base = (year - 1) * 12 + (quarter - 1) * 3
        return [{"month_index": base + i, "focus": None, "objectives": []}
                for i in range(1, 4)]

    monkeypatch.setattr(t, "generate_quarter_plan", fake_gqp)

    results = await t._generate_all_quarters({}, [], {"items": []}, horizon=3)

    assert len(results) == 12  # 3 años × 4 quarters
    assert len(call_count) == 12
    all_months = [m["month_index"] for q in results for m in q]
    assert len(all_months) == 36
    assert sorted(all_months) == list(range(1, 37))
