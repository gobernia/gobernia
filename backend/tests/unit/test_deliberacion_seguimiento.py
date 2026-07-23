"""
La deliberación mensual del Consejo con datos de EJECUCIÓN:
- `avance_tareas`: cómo va el plan (hechas / en proceso / sin ejecutar + arrastradas). El Consejo
  debe evaluar el cumplimiento, no solo los documentos.
- `acuerdos_previos`: los acuerdos abiertos de sesiones anteriores. El Consejo revisa su cumplimiento.

Reglas que se prueban aquí:
- Con los bloques: van al prompt del usuario y el system prompt gana la sección de seguimiento.
- Sin ellos: retrocompat total — funciona como antes, sin la sección de seguimiento.
"""
from types import SimpleNamespace

from app.services.ai.agents.deliberacion import (
    DELIBERACION_SEGUIMIENTO_SYSTEM,
    run_deliberacion,
)

_ANALYSES = {
    "CFO": {"summary": "Margen bajo presión.",
            "recommendations": ["Renegociar proveedores"],
            "alerts": []},
}
_CRITIQUES = {"CFO": {"weak_assumptions": ["asume demanda estable"]}}
_MB = {"company": {"name": "Acme"}}
_ROADMAP = {"pilares": [{"nombre": "Rentabilidad"}], "metas_3anios": ["Crecer"]}

_PAYLOAD = {
    "conclusion": "El Consejo concluye.",
    "avance_roadmap": "Rentabilidad avanza.",
    "riesgos": [],
    "acuerdos": [
        {"texto": "Cerrar caja", "responsable_sugerido": "Finanzas",
         "fecha_sugerida": "2026-09-30", "prioridad": "alta", "pilar": "Rentabilidad",
         "racional": "Ordenar la operación."},
    ],
}


def _mock_ai(monkeypatch, captured: dict):
    monkeypatch.setattr(
        "app.services.ai.agents.deliberacion.settings.ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.services.ai.agents.deliberacion.anthropic.Anthropic", lambda **k: object())
    block = SimpleNamespace(type="tool_use", name="conclusion_consejo", input=_PAYLOAD)

    def _fake(*a, **k):
        captured.update(k)
        return SimpleNamespace(content=[block], stop_reason="tool_use")

    monkeypatch.setattr("app.services.ai.agents.deliberacion._create_with_retry", _fake)


def test_avance_y_acuerdos_previos_van_al_prompt(monkeypatch):
    captured: dict = {}
    _mock_ai(monkeypatch, captured)

    avance = (
        "Totales del plan: 2 completada(s), 1 en proceso, 3 sin ejecutar (de 6 tareas).\n"
        "Tareas arrastradas de meses anteriores (incompletas):\n"
        "  - [sin ejecutar] Firmar contrato — viene de Febrero 2026"
    )
    acuerdos = "  - Contratar auditor · resp. Dirección General · fecha 2026-05-01 · estatus «abierto» — VENCIDO"

    r = run_deliberacion(
        analyses=_ANALYSES, critiques=_CRITIQUES, roadmap=_ROADMAP, memory_buffer=_MB,
        kpi_snapshot=None, period_year=2026, period_month=8,
        avance_tareas=avance, acuerdos_previos=acuerdos,
    )

    assert r["conclusion"] == "El Consejo concluye."

    prompt = captured["messages"][0]["content"]
    assert "AVANCE DEL PLAN" in prompt
    assert "Firmar contrato — viene de Febrero 2026" in prompt
    assert "ACUERDOS PENDIENTES DE SESIONES ANTERIORES" in prompt
    assert "Contratar auditor" in prompt and "VENCIDO" in prompt

    # El system prompt gana la sección de seguimiento (evaluar el cumplimiento).
    assert DELIBERACION_SEGUIMIENTO_SYSTEM in captured["system"]
    assert "EVALÚA EL CUMPLIMIENTO" in captured["system"]


def test_solo_avance_tambien_activa_seguimiento(monkeypatch):
    captured: dict = {}
    _mock_ai(monkeypatch, captured)

    run_deliberacion(
        analyses=_ANALYSES, critiques=_CRITIQUES, roadmap=_ROADMAP, memory_buffer=_MB,
        kpi_snapshot=None, period_year=2026, period_month=8,
        avance_tareas="Totales del plan: 0 completada(s), 0 en proceso, 1 sin ejecutar (de 1 tareas).",
    )
    prompt = captured["messages"][0]["content"]
    assert "AVANCE DEL PLAN" in prompt
    assert "ACUERDOS PENDIENTES" not in prompt
    assert DELIBERACION_SEGUIMIENTO_SYSTEM in captured["system"]


def test_retrocompat_sin_bloques(monkeypatch):
    captured: dict = {}
    _mock_ai(monkeypatch, captured)

    r = run_deliberacion(
        analyses=_ANALYSES, critiques=_CRITIQUES, roadmap=_ROADMAP, memory_buffer=_MB,
        kpi_snapshot=None, period_year=2026, period_month=8,
    )
    assert r["conclusion"] == "El Consejo concluye."

    prompt = captured["messages"][0]["content"]
    assert "AVANCE DEL PLAN" not in prompt
    assert "ACUERDOS PENDIENTES DE SESIONES ANTERIORES" not in prompt
    # Sin datos de ejecución, el system prompt NO gana la sección de seguimiento.
    assert DELIBERACION_SEGUIMIENTO_SYSTEM not in captured["system"]


def test_bloques_vacios_o_espacios_no_activan_seguimiento(monkeypatch):
    captured: dict = {}
    _mock_ai(monkeypatch, captured)

    run_deliberacion(
        analyses=_ANALYSES, critiques=_CRITIQUES, roadmap=_ROADMAP, memory_buffer=_MB,
        kpi_snapshot=None, period_year=2026, period_month=8,
        avance_tareas="   ", acuerdos_previos="",
    )
    assert "AVANCE DEL PLAN" not in captured["messages"][0]["content"]
    assert DELIBERACION_SEGUIMIENTO_SYSTEM not in captured["system"]
