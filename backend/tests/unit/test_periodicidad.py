"""Periodicidad de tareas: mensual (como siempre), trimestral o semestral."""
import asyncio
from types import SimpleNamespace

import pytest

from app.services.periodicidad import (
    etiqueta_periodo, meses_por_periodo, norm_periodicidad, periodicidad_de_onboarding, periodo_de_mes,
)


@pytest.mark.parametrize("entrada, esperado", [
    ("Trimestral", "trimestral"), ("cada 3 meses", "trimestral"), ("Semestral", "semestral"),
    ("cada 6 meses", "semestral"), ("Mensual", "mensual"), (None, "mensual"), ("otra cosa", "mensual"),
])
def test_norm_periodicidad(entrada, esperado):
    assert norm_periodicidad(entrada) == esperado


def test_periodos():
    assert [periodo_de_mes(i, "trimestral") for i in (1, 3, 4, 36)] == [1, 1, 2, 12]
    assert [periodo_de_mes(i, "semestral") for i in (1, 6, 7, 36)] == [1, 1, 2, 6]
    assert periodo_de_mes(5, "mensual") == 5
    assert meses_por_periodo("semestral") == 6


def test_etiquetas():
    assert etiqueta_periodo([(2026, 10), (2026, 12)], "trimestral", 1) == "Trimestre 1 · Oct–Dic 2026"
    assert etiqueta_periodo([(2026, 10), (2027, 3)], "semestral", 1) == "Semestre 1 · Oct 2026–Mar 2027"


def test_periodicidad_de_onboarding():
    assert periodicidad_de_onboarding({"governance": {"periodicidad_tareas": "Trimestral"}}) == "trimestral"
    assert periodicidad_de_onboarding({}) is None


@pytest.mark.parametrize("periodicidad, llamadas, meses_por_bloque", [
    ("trimestral", 12, 3), ("semestral", 6, 6),
])
def test_generacion_por_bloques(monkeypatch, periodicidad, llamadas, meses_por_bloque):
    from app.tasks import annual_plan_tasks as apt
    from app.services.ai.annual_plan_generator import block_month_indices
    vistos = []

    def fake_block(mb, kpis, hitos, year, first_month, p):
        vistos.append((year, first_month, p))
        return [{"month_index": i, "focus": None, "objectives": []}
                for i in block_month_indices(year, first_month, meses_por_bloque)]
    monkeypatch.setattr(apt, "generate_block_plan", fake_block)

    bloques = asyncio.run(apt._generate_all_quarters({}, [], {}, 3, periodicidad))
    assert len(vistos) == llamadas and all(p == periodicidad for *_, p in vistos)
    indices = [m["month_index"] for b in bloques for m in b]
    assert indices == list(range(1, 37))  # los 36 meses, sin huecos ni duplicados


def test_generacion_mensual_sigue_por_trimestres(monkeypatch):
    from app.tasks import annual_plan_tasks as apt
    llamadas = []
    monkeypatch.setattr(apt, "generate_quarter_plan", lambda *a: llamadas.append(a[-2:]) or [])
    asyncio.run(apt._generate_all_quarters({}, [], {}, 3))
    assert len(llamadas) == 12


def test_avance_trimestral_agrupa_el_trimestre_actual():
    from app.api.v1.board_sessions.router import _format_avance_tareas
    meses, tareas = [], {}
    for i in range(1, 7):
        obj = SimpleNamespace(id=f"o{i}")
        meses.append(SimpleNamespace(month_index=i, period_month=i, period_year=2026, objectives=[obj]))
        tareas[obj.id] = [SimpleNamespace(id=i, title=f"Punto {i}", status="pendiente", owner=None, validacion=None)]
    txt = _format_avance_tareas(meses, tareas, active_index=5, periodicidad="trimestral")
    actual, previos = txt.split("arrastradas")
    assert "Trimestre 2 · Abr–Jun 2026" in actual
    assert all(f"Punto {i}" in actual for i in (4, 5, 6))
    assert all(f"Punto {i}" in previos for i in (1, 2, 3))


def test_bloque_con_mas_de_8_puntos_pide_una_correccion(monkeypatch):
    import json
    from app.services.ai import annual_plan_generator as g

    def respuesta(n):
        meses = [{"month_in_period": 1, "objectives": [
            {"title": "O", "tasks": [{"title": f"P{i}"} for i in range(n)]}]}]
        return SimpleNamespace(content=[SimpleNamespace(text=json.dumps({"months": meses}))])

    respuestas = iter([respuesta(11), respuesta(7)])
    llamadas = []
    monkeypatch.setattr(g.settings, "ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(g.anthropic, "Anthropic", lambda **k: object())
    monkeypatch.setattr(g, "_create_with_retry", lambda *a, **k: llamadas.append(k) or next(respuestas))

    meses = g.generate_block_plan({}, [], {}, 1, 1, "trimestral")
    assert g._puntos(meses) == 7 and len(llamadas) == 2
    assert "máximo 8".lower() in llamadas[1]["messages"][-1]["content"].lower()
