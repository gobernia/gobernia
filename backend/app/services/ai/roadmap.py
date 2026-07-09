"""Genera el Roadmap Estratégico a 3 años (documento ejecutivo) desde los datos existentes.
Opus tool-use, sin web. Fallback determinista sin IA. NUNCA inventa el target numérico de las metas."""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry

_MILE = {"type": "object", "properties": {
    "anio1": {"type": "array", "items": {"type": "string"}},
    "anio2": {"type": "array", "items": {"type": "string"}},
    "anio3": {"type": "array", "items": {"type": "string"}},
}}

ROADMAP_TOOL = {
    "name": "roadmap_estrategico",
    "description": "Devuelve el roadmap estratégico a 3 años de la empresa.",
    "input_schema": {
        "type": "object",
        "properties": {
            "vision": {"type": "string"},
            "mision": {"type": "string"},
            "propuesta_valor": {"type": "string"},
            "metas_3anios": {"type": "array", "items": {"type": "object", "properties": {
                "meta": {"type": "string"},
                "kpi": {"type": "string"},
                "valor_actual": {"type": "string"},
                "target": {"type": "string", "description": "DÉJALO VACÍO: lo fija el dueño. No inventes."},
            }, "required": ["meta"]}},
            "resumen_foda": {"type": "string"},
            "resumen_entorno": {"type": "string"},
            "pilares": {"type": "array", "items": {"type": "object", "properties": {
                "nombre": {"type": "string"},
                "descripcion": {"type": "string"},
                "milestones": _MILE,
            }, "required": ["nombre", "descripcion"]}},
        },
        "required": ["vision", "mision", "propuesta_valor", "metas_3anios",
                     "resumen_foda", "resumen_entorno", "pilares"],
    },
}

_SYSTEM = (
    "Eres el consejo estratégico de Gobernia. Redacta el ROADMAP ESTRATÉGICO a 3 años de la empresa, "
    "en español, con lenguaje EJECUTIVO, claro e INSPIRADOR: es el documento que el dueño y sus "
    "directivos usarán para comunicación interna, gobernanza e inversión de recursos.\n"
    "- Deriva los PILARES estratégicos (3-5) del FODA y el diagnóstico (ej. Excelencia operacional, "
    "Expansión de mercado, Innovación). Cada pilar con una descripción breve y milestones TANGIBLES y "
    "MEDIBLES por año (2-4 por año).\n"
    "- Para 'metas_3anios' usa los KPIs reales: propón la meta y su 'kpi', pon 'valor_actual' si lo "
    "conoces, y deja 'target' VACÍO (el dueño lo fijará; NUNCA inventes el número).\n"
    "- 'resumen_foda' y 'resumen_entorno': síntesis ejecutiva breve.\n"
    "No inventes datos que no estén en la información dada."
)


def _kpis_metas(memory_buffer: dict) -> list[dict]:
    out = []
    for _cat, items in ((memory_buffer or {}).get("kpis") or {}).items():
        for k in (items or []):
            if not isinstance(k, dict):
                continue
            label = str(k.get("label") or "").strip()
            if not label:
                continue
            val = k.get("current_value")
            va = f"{val}{k.get('unit') or ''}" if val is not None else None
            out.append({"meta": f"Mejorar {label.lower()}", "kpi": label, "valor_actual": va, "target": ""})
    return out[:6]


def _roadmap_fallback(memory_buffer: dict, diagnostico_content: dict) -> dict:
    vision = str(((memory_buffer or {}).get("vision") or {}).get("statement") or "").strip()
    foda = (diagnostico_content or {}).get("foda") or {}
    return {
        "vision": vision,
        "mision": "",
        "propuesta_valor": "",
        "metas_3anios": _kpis_metas(memory_buffer),
        "resumen_foda": str(foda.get("sintesis") or "").strip(),
        "resumen_entorno": "",
        "pilares": [],
    }


def _norm_lista(v) -> list[str]:
    return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []


def generate_roadmap(memory_buffer: dict, diagnostico_content: dict) -> dict:
    if not settings.ANTHROPIC_API_KEY:
        return _roadmap_fallback(memory_buffer, diagnostico_content)
    c = (memory_buffer or {}).get("company") or {}
    dcont = diagnostico_content or {}
    user = (
        f"EMPRESA: {json.dumps(c, ensure_ascii=False)[:1500]}\n"
        f"VISIÓN ACTUAL: {((memory_buffer or {}).get('vision') or {}).get('statement') or '(n/d)'}\n"
        f"DEFINICIÓN DE ÉXITO DEL DUEÑO (lo que haría que valga la pena el consejo — ORIENTA el roadmap "
        f"hacia esto): {((memory_buffer or {}).get('vision') or {}).get('exito_consejo') or '(n/d)'}\n"
        f"KPIs: {json.dumps((memory_buffer or {}).get('kpis') or {}, ensure_ascii=False)[:1500]}\n"
        f"HALLAZGOS INTERNOS: {json.dumps(dcont.get('fortalezas_debilidades') or {}, ensure_ascii=False)[:2000]}\n"
        f"RIESGOS: {json.dumps(dcont.get('riesgos') or [], ensure_ascii=False)[:1200]}\n"
        f"FODA: {json.dumps(dcont.get('foda') or {}, ensure_ascii=False)[:2000]}\n"
        f"FACTORES EXTERNOS: {json.dumps(dcont.get('factores_externos') or {}, ensure_ascii=False)[:1500]}\n"
        f"METAS PRIORIZADAS: {json.dumps(dcont.get('metas_orden') or [], ensure_ascii=False)[:800]}\n\n"
        "Redacta el roadmap en el JSON indicado."
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=300.0)
        response = _create_with_retry(
            client, model=settings.DIAGNOSTICO_AI_MODEL, max_tokens=3072,
            system=_SYSTEM, messages=[{"role": "user", "content": user}],
            tools=[ROADMAP_TOOL], tool_choice={"type": "tool", "name": "roadmap_estrategico"},
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        d = dict(block.input) if block and isinstance(block.input, dict) else {}
        if not d:
            return _roadmap_fallback(memory_buffer, diagnostico_content)
        metas = []
        for m in (d.get("metas_3anios") or []):
            if isinstance(m, dict) and str(m.get("meta") or "").strip():
                metas.append({"meta": str(m["meta"]).strip(), "kpi": (str(m.get("kpi")).strip() or None) if m.get("kpi") else None,
                              "valor_actual": (str(m.get("valor_actual")).strip() or None) if m.get("valor_actual") else None,
                              "target": ""})
        metas = metas[:6]
        pilares = []
        for p in (d.get("pilares") or []):
            if not isinstance(p, dict) or not str(p.get("nombre") or "").strip():
                continue
            mi = p.get("milestones") or {}
            pilares.append({"nombre": str(p["nombre"]).strip(), "descripcion": str(p.get("descripcion") or "").strip(),
                            "milestones": {"anio1": _norm_lista(mi.get("anio1")),
                                           "anio2": _norm_lista(mi.get("anio2")),
                                           "anio3": _norm_lista(mi.get("anio3"))}})
        return {
            "vision": str(d.get("vision") or "").strip(),
            "mision": str(d.get("mision") or "").strip(),
            "propuesta_valor": str(d.get("propuesta_valor") or "").strip(),
            "metas_3anios": metas,
            "resumen_foda": str(d.get("resumen_foda") or "").strip(),
            "resumen_entorno": str(d.get("resumen_entorno") or "").strip(),
            "pilares": pilares,
        }
    except Exception:
        return _roadmap_fallback(memory_buffer, diagnostico_content)
