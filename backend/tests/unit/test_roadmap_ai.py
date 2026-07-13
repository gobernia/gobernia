# backend/tests/unit/test_roadmap_ai.py
"""Roadmap Estratégico: campos del template de presentación (todos opcionales).

Reglas duras:
- La IA NUNCA fija un número meta: `metas_3anios[].target` y `pilares[].kpis[].meta`
  SIEMPRE salen como "" (los fija el dueño).
- El template es una guía: lo que la IA no puede sustentar queda VACÍO, sin reventar.
- El fallback devuelve exactamente el mismo shape que la rama de IA.
"""
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.ai.roadmap import _roadmap_fallback, generate_roadmap

_KEYS = {
    "vision", "mision", "propuesta_valor", "metas_3anios", "resumen_foda",
    "resumen_entorno", "pilares",
    # nuevos (globales)
    "anio_objetivo", "objetivos_estrategicos", "key_enablers", "temas_por_anio",
    "conclusion_diagnostico", "conclusion_entorno",
}
_PILAR_KEYS = {
    "nombre", "descripcion", "milestones",
    # nuevos (por pilar)
    "objetivo", "estrategias", "kpis", "resultados_esperados", "fases",
}


def _mock_ai(monkeypatch, payload: dict):
    monkeypatch.setattr("app.services.ai.roadmap.settings.ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("app.services.ai.roadmap.anthropic.Anthropic", lambda **k: object())
    block = SimpleNamespace(type="tool_use", input=payload)
    monkeypatch.setattr(
        "app.services.ai.roadmap._create_with_retry",
        lambda *a, **k: SimpleNamespace(content=[block]),
    )


# ── Test A: esquema completo nuevo ───────────────────────────────────────────
def test_ai_normaliza_todos_los_campos_nuevos_y_jamas_inventa_metas(monkeypatch):
    _mock_ai(monkeypatch, {
        "vision": "Ser referente regional",
        "mision": "Servir con excelencia",
        "propuesta_valor": "Cercanía + calidad",
        "anio_objetivo": 2029,
        "objetivos_estrategicos": ["Rentabilizar", "  Expandir  ", ""],
        "key_enablers": ["Talento", "Tecnología"],
        "temas_por_anio": {"anio1": "Ordenar la casa", "anio2": "Expandir el negocio",
                           "anio3": "Consolidar el liderazgo"},
        "conclusion_diagnostico": "Base sólida, márgenes bajo presión.",
        "conclusion_entorno": "El mercado se consolida; hay ventana de 24 meses.",
        "metas_3anios": [{"meta": "Elevar margen", "kpi": "Margen neto",
                          "valor_actual": "6%", "target": "15%"}],
        "resumen_foda": "FODA",
        "resumen_entorno": "Entorno",
        "pilares": [{
            "nombre": "Excelencia operacional",
            "descripcion": "Eficiencia en la operación",
            "objetivo": "Reducir el costo por unidad",
            "estrategias": ["Automatizar", "Renegociar proveedores"],
            "kpis": [{"label": "Margen bruto", "actual": "28%", "meta": "40%"}],
            "resultados_esperados": [{"titulo": "↑ Margen bruto", "descripcion": "Mayor rentabilidad"}],
            "fases": {"anio1": {"titulo": "Estabilizar"}, "anio2": {"titulo": "Escalar"},
                      "anio3": {"titulo": "Optimizar"}},
            "milestones": {"anio1": ["Mapa de procesos"], "anio2": ["ERP"], "anio3": ["Certificación"]},
        }],
    })

    r = generate_roadmap({"company": {"name": "Acme"}}, {})

    assert set(r.keys()) == _KEYS
    assert r["anio_objetivo"] == 2029
    assert r["objetivos_estrategicos"] == ["Rentabilizar", "Expandir"]
    assert r["key_enablers"] == ["Talento", "Tecnología"]
    assert r["temas_por_anio"] == {"anio1": "Ordenar la casa", "anio2": "Expandir el negocio",
                                   "anio3": "Consolidar el liderazgo"}
    assert r["conclusion_diagnostico"].startswith("Base sólida")
    assert r["conclusion_entorno"].startswith("El mercado")

    # INVARIANTE: nunca inventa el número meta
    assert r["metas_3anios"][0]["target"] == ""

    p = r["pilares"][0]
    assert set(p.keys()) == _PILAR_KEYS
    assert p["objetivo"] == "Reducir el costo por unidad"
    assert p["estrategias"] == ["Automatizar", "Renegociar proveedores"]
    assert p["kpis"] == [{"label": "Margen bruto", "actual": "28%", "meta": ""}]  # meta SIEMPRE ""
    assert p["resultados_esperados"] == [{"titulo": "↑ Margen bruto", "descripcion": "Mayor rentabilidad"}]
    assert p["fases"] == {"anio1": {"titulo": "Estabilizar"}, "anio2": {"titulo": "Escalar"},
                          "anio3": {"titulo": "Optimizar"}}
    assert p["milestones"]["anio1"] == ["Mapa de procesos"]


# ── Test B: esquema viejo (la IA no llena lo que no sustenta) ────────────────
def test_ai_esquema_viejo_deja_campos_nuevos_vacios(monkeypatch):
    _mock_ai(monkeypatch, {
        "vision": "V", "mision": "M", "propuesta_valor": "PV",
        "metas_3anios": [{"meta": "Meta 1"}],
        "resumen_foda": "F", "resumen_entorno": "E",
        "pilares": [{"nombre": "Pilar", "descripcion": "D",
                     "milestones": {"anio1": ["a"], "anio2": [], "anio3": []}}],
    })

    r = generate_roadmap({}, {})

    assert set(r.keys()) == _KEYS
    assert r["anio_objetivo"] == date.today().year + 3  # default
    assert r["objetivos_estrategicos"] == [] and r["key_enablers"] == []
    assert r["temas_por_anio"] == {"anio1": "", "anio2": "", "anio3": ""}
    assert r["conclusion_diagnostico"] == "" and r["conclusion_entorno"] == ""

    p = r["pilares"][0]
    assert set(p.keys()) == _PILAR_KEYS
    assert p["objetivo"] == ""
    assert p["estrategias"] == [] and p["kpis"] == [] and p["resultados_esperados"] == []
    assert p["fases"] == {"anio1": {"titulo": ""}, "anio2": {"titulo": ""}, "anio3": {"titulo": ""}}


# ── Test C: el fallback tiene el mismo shape que la rama de IA ───────────────
def test_fallback_mismo_shape_que_rama_ai(monkeypatch):
    _mock_ai(monkeypatch, {
        "vision": "V", "mision": "M", "propuesta_valor": "PV",
        "metas_3anios": [], "resumen_foda": "F", "resumen_entorno": "E", "pilares": [],
    })
    ai = generate_roadmap({}, {})
    fb = _roadmap_fallback(
        {"vision": {"statement": "V"},
         "kpis": {"financiero": [{"label": "Margen neto", "current_value": 6, "unit": "%"}]}},
        {"foda": {"sintesis": "S"}},
    )
    assert set(fb.keys()) == set(ai.keys()) == _KEYS
    assert fb["metas_3anios"][0]["target"] == ""  # tampoco inventa en el fallback
    assert fb["temas_por_anio"] == {"anio1": "", "anio2": "", "anio3": ""}
    assert fb["anio_objetivo"] == date.today().year + 3
    assert fb["objetivos_estrategicos"] == [] and fb["key_enablers"] == []
    assert fb["pilares"] == []


# ── Robustez: shapes raros de la IA no revientan ─────────────────────────────
@pytest.mark.parametrize("basura", [
    {"objetivos_estrategicos": "no soy lista", "key_enablers": {"a": 1},
     "temas_por_anio": "no soy dict", "anio_objetivo": "dos mil treinta"},
    {"objetivos_estrategicos": None, "temas_por_anio": {"anio1": ["x"]}, "anio_objetivo": None},
])
def test_ai_shapes_raros_no_revientan(monkeypatch, basura):
    payload = {
        "vision": "V", "mision": "M", "propuesta_valor": "PV",
        "metas_3anios": ["no soy dict", {"meta": "OK"}],
        "resumen_foda": "F", "resumen_entorno": "E",
        "pilares": ["no soy dict", {
            "nombre": "P", "descripcion": "D",
            "estrategias": "no soy lista",
            "kpis": "no soy lista",
            "resultados_esperados": [{"titulo": "T"}, "basura"],
            "fases": "no soy dict",
            "milestones": "no soy dict",
        }],
        **basura,
    }
    _mock_ai(monkeypatch, payload)
    r = generate_roadmap({}, {})

    assert set(r.keys()) == _KEYS
    assert isinstance(r["anio_objetivo"], int)
    assert r["objetivos_estrategicos"] == [] and r["key_enablers"] == []
    assert set(r["temas_por_anio"]) == {"anio1", "anio2", "anio3"}
    assert all(isinstance(v, str) for v in r["temas_por_anio"].values())
    assert [m["meta"] for m in r["metas_3anios"]] == ["OK"]

    p = r["pilares"][0]
    assert set(p.keys()) == _PILAR_KEYS
    assert p["estrategias"] == [] and p["kpis"] == []
    assert p["resultados_esperados"] == [{"titulo": "T", "descripcion": ""}]
    assert p["fases"] == {"anio1": {"titulo": ""}, "anio2": {"titulo": ""}, "anio3": {"titulo": ""}}
    assert p["milestones"] == {"anio1": [], "anio2": [], "anio3": []}
