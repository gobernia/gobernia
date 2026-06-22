"""Motor de la matriz FODA: síntesis de lo interno (hallazgos) + externo (factores) + metas.
Opus sin web_search, salida estructurada por tool use. Fallback determinista si no hay IA."""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry

FODA_TOOL = {
    "name": "matriz_foda",
    "description": "Devuelve la matriz FODA de la empresa.",
    "input_schema": {
        "type": "object",
        "properties": {
            "fortalezas": {"type": "array", "items": {"type": "string"}},
            "oportunidades": {"type": "array", "items": {"type": "string"}},
            "debilidades": {"type": "array", "items": {"type": "string"}},
            "amenazas": {"type": "array", "items": {"type": "string"}},
            "sintesis": {"type": "string"},
        },
        "required": ["fortalezas", "oportunidades", "debilidades", "amenazas", "sintesis"],
    },
}


def _texts_by_tipo(d: dict, tipos: set) -> list[str]:
    out = []
    for items in (d or {}).values():
        for it in (items or []):
            if str((it or {}).get("tipo")) in tipos and str((it or {}).get("texto", "")).strip():
                out.append(str(it["texto"]).strip())
    return out


def _foda_fallback(hallazgos: dict, factores_externos: dict, metas_orden: list) -> dict:
    return {
        "fortalezas": _texts_by_tipo(hallazgos, {"fortaleza"}),
        "debilidades": _texts_by_tipo(hallazgos, {"debilidad", "parcial"}),
        "oportunidades": _texts_by_tipo(factores_externos, {"oportunidad"}),
        "amenazas": _texts_by_tipo(factores_externos, {"amenaza"}),
        "sintesis": "",
        "metas_priorizadas": [str(m) for m in (metas_orden or [])],
    }


_SYSTEM = (
    "Eres un analista estratégico senior del consejo de Gobernia. Construye la matriz FODA de la empresa "
    "en español, integrando lo INTERNO (fortalezas/debilidades de la entrevista) con lo EXTERNO "
    "(oportunidades/amenazas del entorno) y el diagnóstico. Sé concreto y accionable: 3-6 puntos por "
    "cuadrante, frases cortas. En 'sintesis' (2-3 oraciones) cruza lo más importante: cómo usar las "
    "fortalezas para las oportunidades y qué debilidades/amenazas atender primero, considerando las "
    "metas prioritarias del dueño. No inventes datos que no estén en la información dada."
)


def generate_foda(memory_buffer: dict, diagnostico_content: dict,
                  factores_externos: dict, metas_orden: list) -> dict:
    hallazgos = ((diagnostico_content or {}).get("fortalezas_debilidades")
                 or (memory_buffer or {}).get("hallazgos") or {})
    fallback = _foda_fallback(hallazgos, factores_externos, metas_orden)
    if not settings.ANTHROPIC_API_KEY:
        return fallback

    secciones = []
    for s in ((diagnostico_content or {}).get("sections") or [])[:4]:
        if s.get("body"):
            secciones.append(f"{s.get('title','')}: {s['body'][:600]}")
    user = (
        "HALLAZGOS INTERNOS:\n" + json.dumps(hallazgos, ensure_ascii=False)[:2500] + "\n\n"
        "FACTORES EXTERNOS:\n" + json.dumps(factores_externos or {}, ensure_ascii=False)[:2500] + "\n\n"
        "DIAGNÓSTICO (web):\n" + ("\n".join(secciones) or "(n/d)")[:2500] + "\n\n"
        "METAS PRIORITARIAS (en orden):\n" + json.dumps([str(m) for m in (metas_orden or [])], ensure_ascii=False)
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=300.0)
        response = _create_with_retry(
            client, model=settings.DIAGNOSTICO_AI_MODEL, max_tokens=2048,
            system=_SYSTEM, messages=[{"role": "user", "content": user}],
            tools=[FODA_TOOL], tool_choice={"type": "tool", "name": "matriz_foda"},
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        d = dict(block.input) if block is not None and isinstance(block.input, dict) else {}
        if not d:
            return fallback
        return {
            "fortalezas": [str(x) for x in (d.get("fortalezas") or [])],
            "oportunidades": [str(x) for x in (d.get("oportunidades") or [])],
            "debilidades": [str(x) for x in (d.get("debilidades") or [])],
            "amenazas": [str(x) for x in (d.get("amenazas") or [])],
            "sintesis": str(d.get("sintesis") or ""),
            "metas_priorizadas": [str(m) for m in (metas_orden or [])],
        }
    except Exception:
        return fallback
