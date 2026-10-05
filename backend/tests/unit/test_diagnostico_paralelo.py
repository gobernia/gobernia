"""El diagnóstico inicial corre a los 4 consejeros en paralelo, sin mezclar resultados."""
import time


def test_run_diagnostico_en_paralelo(monkeypatch):
    from app.services.ai.agents import base
    from app.tasks.annual_plan_tasks import run_diagnostico

    def analisis(agent, *a, **k):
        time.sleep(0.5)
        return {"summary": f"análisis de {agent}"}

    def critica(agent, initial, *a, **k):
        time.sleep(0.5)
        return {"de": agent}

    def revision(agent, initial, critique, *a, **k):
        time.sleep(0.5)
        return {**initial, "revisado": agent}

    monkeypatch.setattr(base, "run_agent_analysis", analisis)
    monkeypatch.setattr(base, "run_challenger_critique", critica)
    monkeypatch.setattr(base, "run_agent_revision", revision)

    t0 = time.monotonic()
    analyses, critiques = run_diagnostico({"kpis": {}})
    duracion = time.monotonic() - t0

    assert list(analyses) == ["CFO", "CSO", "CRO", "Auditor"]
    assert all(analyses[a] == {"summary": f"análisis de {a}", "revisado": a} for a in analyses)
    assert all(critiques[a] == {"de": a} for a in critiques)
    assert duracion < 3, f"tardó {duracion:.1f}s (en fila serían ~6s)"
