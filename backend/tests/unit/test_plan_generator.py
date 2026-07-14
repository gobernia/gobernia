"""
Generador del plan de acción: consume los análisis del consejo, donde las alertas
son dicts {nivel, texto, fuente} desde el board pack.
"""
from app.services.ai.plan_generator import _fallback_plan_from_analyses


def test_fallback_usa_el_texto_de_la_alerta_no_el_dict_crudo():
    """Regresión: str(dict) titulaba la tarea "{'nivel': 'rojo', ...}"."""
    tasks = _fallback_plan_from_analyses({
        "CFO": {
            "summary": "S",
            "alerts": [{"nivel": "rojo", "texto": "Liquidez crítica", "fuente": "Balance, p. 2"}],
            "recommendations": [],
        }
    })
    assert [t["title"] for t in tasks] == ["Liquidez crítica"]
    assert tasks[0]["priority"] == "alta"
    assert tasks[0]["source_agent"] == "CFO"


def test_fallback_tolera_alertas_legacy_en_string():
    tasks = _fallback_plan_from_analyses({
        "CRO": {"summary": "S", "alerts": ["Riesgo cambiario"], "recommendations": []}
    })
    assert [t["title"] for t in tasks] == ["Riesgo cambiario"]


def test_fallback_ignora_alertas_sin_texto():
    tasks = _fallback_plan_from_analyses({
        "CSO": {
            "summary": "S",
            "alerts": [{"nivel": "verde", "texto": "", "fuente": ""}, {}, None],
            "recommendations": ["Contratar director comercial"],
        }
    })
    assert [t["title"] for t in tasks] == ["Contratar director comercial"]


def test_fallback_conserva_recomendaciones_y_orden():
    tasks = _fallback_plan_from_analyses({
        "Auditor": {
            "summary": "S",
            "alerts": [{"nivel": "ambar", "texto": "Falta acta"}],
            "recommendations": ["Levantar minuta"],
        }
    })
    assert [t["title"] for t in tasks] == ["Falta acta", "Levantar minuta"]
    assert [t["order_index"] for t in tasks] == [0, 1]
