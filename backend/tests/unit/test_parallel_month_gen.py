import pytest

import app.tasks.annual_plan_tasks as t


@pytest.mark.asyncio
async def test_genera_12_meses_en_orden(monkeypatch):
    calls = []

    def fake_gmt(focus, objectives, memory_buffer, year, month):
        calls.append(month)
        return [{"focus": focus, "month": month}]

    monkeypatch.setattr(t, "generate_month_tasks", fake_gmt)
    skeleton = [{"month_index": i, "focus": f"f{i}", "objectives": []} for i in range(1, 13)]

    res = await t._generate_all_month_tasks(skeleton, {}, 2026, 1)

    assert len(res) == 12
    assert len(calls) == 12  # se llamaron los 12 meses
    # gather preserva el orden del esqueleto
    assert res[0][0]["focus"] == "f1"
    assert res[11][0]["focus"] == "f12"
    # mapeo correcto a mes calendario (start enero 2026)
    assert res[0][0]["month"] == 1
    assert res[11][0]["month"] == 12
