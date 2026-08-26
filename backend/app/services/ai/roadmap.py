"""Genera el Roadmap Estratégico a 3 años (documento ejecutivo) desde los datos existentes.
Opus tool-use, sin web. Fallback determinista sin IA. NUNCA inventa el target numérico de las metas."""
import json
from datetime import date

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry
from app.services.ai.prompt_loader import load_prompt

_ANIOS = ("anio1", "anio2", "anio3")

_MILE = {"type": "object", "properties": {
    "anio1": {"type": "array", "items": {"type": "string"}},
    "anio2": {"type": "array", "items": {"type": "string"}},
    "anio3": {"type": "array", "items": {"type": "string"}},
}}

_FASES = {"type": "object", "description": "Título de la fase de cada año para este pilar.",
          "properties": {a: {"type": "object", "properties": {"titulo": {"type": "string"}}}
                         for a in _ANIOS}}

_TEMAS = {"type": "object", "description": "Lema/tema de cada año (ej. 'Ordenar la casa').",
          "properties": {a: {"type": "string"} for a in _ANIOS}}

ROADMAP_TOOL = {
    "name": "roadmap_estrategico",
    "description": "Devuelve el roadmap estratégico a 3 años de la empresa.",
    "input_schema": {
        "type": "object",
        "properties": {
            "vision": {"type": "string"},
            "mision": {"type": "string"},
            "propuesta_valor": {"type": "string"},
            "anio_objetivo": {"type": "integer", "description": "Año horizonte del plan (año actual + 3)."},
            "objetivos_estrategicos": {"type": "array", "items": {"type": "string"},
                                       "description": "Objetivos estratégicos de alto nivel (opcional)."},
            "key_enablers": {"type": "array", "items": {"type": "string"},
                             "description": "Habilitadores transversales: talento, tecnología, capital, gobernanza… (opcional)."},
            "temas_por_anio": _TEMAS,
            "conclusion_diagnostico": {"type": "string",
                                       "description": "Conclusión ejecutiva del diagnóstico interno (opcional)."},
            "conclusion_entorno": {"type": "string",
                                   "description": "Conclusión estratégica de las tendencias externas (opcional)."},
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
                "razon": {"type": "string",
                          "description": "Por qué esta prioridad IMPORTA para la empresa, en 1 frase concreta (opcional)."},
                "objetivo": {"type": "string", "description": "Objetivo estratégico del pilar (opcional)."},
                "estrategias": {"type": "array", "items": {"type": "string"},
                                "description": "0-4 estrategias principales del pilar (opcional)."},
                "riesgos": {"type": "array", "items": {"type": "string"},
                            "description": "0-3 riesgos CONCRETOS de esta prioridad, tomados de los que señaló el Consejo cuando apliquen (opcional)."},
                "kpis": {"type": "array", "description": "0-3 KPIs del pilar (opcional).",
                         "items": {"type": "object", "properties": {
                             "label": {"type": "string"},
                             "actual": {"type": "string", "description": "Valor actual, si lo conoces."},
                             "meta": {"type": "string", "description": "DÉJALO VACÍO: lo fija el dueño. No inventes."},
                         }, "required": ["label"]}},
                "resultados_esperados": {"type": "array", "description": "0-3 resultados esperados (opcional).",
                                         "items": {"type": "object", "properties": {
                                             "titulo": {"type": "string", "description": "Corto, tipo '↑ Margen bruto'."},
                                             "descripcion": {"type": "string"},
                                         }, "required": ["titulo"]}},
                "fases": _FASES,
                "milestones": _MILE,
                "temas_consejo": {"type": "array", "items": {"type": "string"},
                                  "description": "0-3 asuntos que el Consejo deberá revisar durante el año para asegurar avance del pilar (opcional; solo si puede sustentarse)."},
            }, "required": ["nombre", "descripcion"]}},
        },
        "required": ["vision", "mision", "propuesta_valor", "metas_3anios",
                     "resumen_foda", "resumen_entorno", "pilares"],
    },
}

_SYSTEM = load_prompt("roadmap_system")  # editable en backend/prompts/roadmap_system.md


# Cuando el Consejo ya deliberó, el Roadmap deja de ser una redacción libre: es la TRADUCCIÓN de
# esa postura a un plan de 3 años. Los pilares se derivan de las prioridades del Consejo.
_SYSTEM_CONSEJO = "\n\n" + load_prompt("roadmap_consejo")  # editable en backend/prompts/roadmap_consejo.md


def _anio_objetivo_default() -> int:
    return date.today().year + 3


def _deliberacion_ctx(deliberacion: dict | None) -> str:
    """El bloque de prompt con la postura del Consejo. Vacío si el Consejo no deliberó."""
    d = deliberacion or {}
    if not str(d.get("conclusion") or "").strip():
        return ""
    prioridades = [str(p).strip() for p in (d.get("prioridades") or []) if str(p).strip()]
    riesgos = [
        f"[{str(r.get('nivel') or 'ambar')}] {str(r.get('texto') or '').strip()}"
        for r in (d.get("riesgos") or [])
        if isinstance(r, dict) and str(r.get("texto") or "").strip()
    ]
    return (
        "\n=== POSTURA DEL CONSEJO DE ADMINISTRACIÓN (de aquí NACE este roadmap) ===\n"
        f"CONCLUSIÓN DEL CONSEJO:\n{str(d['conclusion']).strip()}\n\n"
        f"TESIS ESTRATÉGICA (la apuesta que el roadmap debe hacer realidad):\n"
        f"{str(d.get('tesis_estrategica') or '(n/d)').strip()}\n\n"
        "PRIORIDADES DEL CONSEJO, EN ORDEN (de aquí derivas los PILARES):\n"
        + ("\n".join(f"  {i}. {p}" for i, p in enumerate(prioridades, 1)) or "  (n/d)")
        + "\n\nRIESGOS QUE EL CONSEJO PUSO SOBRE LA MESA (el roadmap debe atenderlos):\n"
        + ("\n".join(f"  - {r}" for r in riesgos) or "  (ninguno)")
        + "\n=== FIN DE LA POSTURA DEL CONSEJO ===\n\n"
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


def _norm_lista(v) -> list[str]:
    return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []


def _norm_temas(v) -> dict:
    """{anio1,anio2,anio3} -> str. Tolera dicts raros / no-dicts."""
    d = v if isinstance(v, dict) else {}
    return {a: (str(d.get(a)).strip() if isinstance(d.get(a), (str, int, float)) else "") for a in _ANIOS}


def _norm_kpis(v) -> list[dict]:
    """0-3 KPIs {label, actual, meta}. 'meta' SIEMPRE "" — la IA nunca fija el número."""
    out = []
    for k in (v if isinstance(v, list) else []):
        if not isinstance(k, dict):
            continue
        label = str(k.get("label") or "").strip()
        if not label:
            continue
        out.append({"label": label, "actual": str(k.get("actual") or "").strip(), "meta": ""})
    return out[:3]


def _norm_resultados(v) -> list[dict]:
    out = []
    for r in (v if isinstance(v, list) else []):
        if not isinstance(r, dict):
            continue
        titulo = str(r.get("titulo") or "").strip()
        if not titulo:
            continue
        out.append({"titulo": titulo, "descripcion": str(r.get("descripcion") or "").strip()})
    return out[:3]


def _norm_fases(v) -> dict:
    """{anio1,anio2,anio3} -> {"titulo": str}. Tolera shapes raros."""
    d = v if isinstance(v, dict) else {}
    out = {}
    for a in _ANIOS:
        f = d.get(a)
        if isinstance(f, dict):
            titulo = str(f.get("titulo") or "").strip()
        elif isinstance(f, (str, int, float)):
            titulo = str(f).strip()
        else:
            titulo = ""
        out[a] = {"titulo": titulo}
    return out


def _norm_anio(v) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return _anio_objetivo_default()
    return n if 2000 <= n <= 2100 else _anio_objetivo_default()


def _roadmap_fallback(memory_buffer: dict, diagnostico_content: dict) -> dict:
    vision = str(((memory_buffer or {}).get("vision") or {}).get("statement") or "").strip()
    foda = (diagnostico_content or {}).get("foda") or {}
    return {
        "vision": vision,
        "mision": "",
        "propuesta_valor": "",
        "anio_objetivo": _anio_objetivo_default(),
        "objetivos_estrategicos": [],
        "key_enablers": [],
        "temas_por_anio": _norm_temas(None),
        "conclusion_diagnostico": "",
        "conclusion_entorno": "",
        "metas_3anios": _kpis_metas(memory_buffer),
        "resumen_foda": str(foda.get("sintesis") or "").strip(),
        "resumen_entorno": "",
        "pilares": [],
    }


def generate_roadmap(memory_buffer: dict, diagnostico_content: dict,
                     deliberacion: dict | None = None) -> dict:
    """
    El Roadmap Estratégico a 3 años.

    `deliberacion` (opcional): la postura fundacional del Consejo
    ({conclusion, prioridades, riesgos, tesis_estrategica}). Si viene, el roadmap deja de
    escribirse de cero: es la TRADUCCIÓN de lo que el Consejo deliberó, y sus pilares se derivan
    de las prioridades del órgano. Sin ella, se comporta como siempre (retrocompatible).
    """
    if not settings.ANTHROPIC_API_KEY:
        return _roadmap_fallback(memory_buffer, diagnostico_content)
    c = (memory_buffer or {}).get("company") or {}
    dcont = diagnostico_content or {}
    consejo = _deliberacion_ctx(deliberacion)
    user = (
        f"{consejo}"
        f"EMPRESA: {json.dumps(c, ensure_ascii=False)[:1500]}\n"
        f"AÑO ACTUAL: {date.today().year} (horizonte del plan: {_anio_objetivo_default()})\n"
        f"VISIÓN ACTUAL: {((memory_buffer or {}).get('vision') or {}).get('statement') or '(n/d)'}\n"
        f"DEFINICIÓN DE ÉXITO DEL DUEÑO (lo que haría que valga la pena el consejo — ORIENTA el roadmap "
        f"hacia esto): {((memory_buffer or {}).get('vision') or {}).get('exito_consejo') or '(n/d)'}\n"
        f"KPIs: {json.dumps((memory_buffer or {}).get('kpis') or {}, ensure_ascii=False)[:1500]}\n"
        f"HALLAZGOS INTERNOS: {json.dumps(dcont.get('fortalezas_debilidades') or {}, ensure_ascii=False)[:2000]}\n"
        f"RIESGOS: {json.dumps(dcont.get('riesgos') or [], ensure_ascii=False)[:1200]}\n"
        f"FODA: {json.dumps(dcont.get('foda') or {}, ensure_ascii=False)[:2000]}\n"
        f"FACTORES EXTERNOS: {json.dumps(dcont.get('factores_externos') or {}, ensure_ascii=False)[:1500]}\n"
        f"METAS PRIORIZADAS: {json.dumps(dcont.get('metas_orden') or [], ensure_ascii=False)[:800]}\n\n"
        + ("Traduce la postura del Consejo al roadmap, en el JSON indicado."
           if consejo else "Redacta el roadmap en el JSON indicado.")
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=300.0)

        def _llamar(extra: str = "") -> dict:
            # max_tokens amplio: el JSON completo con 5 pilares (estrategias, kpis,
            # fases y milestones de 3 años) NO cabía en 4096 y el modelo truncaba
            # justo en 'pilares' (el campo más pesado, al final del esquema).
            response = _create_with_retry(
                client, model=settings.DIAGNOSTICO_AI_MODEL, max_tokens=8192,
                system=_SYSTEM + (_SYSTEM_CONSEJO if consejo else ""),
                messages=[{"role": "user", "content": user + extra}],
                tools=[ROADMAP_TOOL], tool_choice={"type": "tool", "name": "roadmap_estrategico"},
            )
            block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
            return dict(block.input) if block and isinstance(block.input, dict) else {}

        d = _llamar()
        if not d:
            return _roadmap_fallback(memory_buffer, diagnostico_content)
        out = _parse_roadmap_dict(d)

        # Los PILARES son el corazón del roadmap: sin ellos no hay prioridades,
        # ni Plan anual, ni tablero. Si vinieron vacíos (truncación o respuesta
        # tímida), se reintenta UNA vez pidiéndolos de forma explícita.
        if not out["pilares"]:
            d2 = _llamar(
                "\n\nATENCIÓN: tu respuesta anterior dejó el campo 'pilares' VACÍO y eso "
                "invalida el roadmap. Los PILARES son OBLIGATORIOS: entrega entre 3 y 5, "
                "derivados de los objetivos y prioridades de la empresa, cada uno con "
                "nombre, descripcion, estrategias, kpis, fases y milestones por año."
            )
            if d2:
                out2 = _parse_roadmap_dict(d2)
                if out2["pilares"]:
                    out = out2

        # Último recurso: derivar pilares mínimos de los objetivos estratégicos,
        # para que el plan NUNCA quede sin prioridades (el dueño los puede editar).
        if not out["pilares"]:
            out["pilares"] = _pilares_desde_objetivos(out)
        return out
    except Exception:
        return _roadmap_fallback(memory_buffer, diagnostico_content)


def _parse_roadmap_dict(d: dict) -> dict:
    """Normaliza la respuesta cruda del modelo al shape canónico del roadmap."""
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
        mi = p.get("milestones") if isinstance(p.get("milestones"), dict) else {}
        pilares.append({"nombre": str(p["nombre"]).strip(),
                        "descripcion": str(p.get("descripcion") or "").strip(),
                        "razon": str(p.get("razon") or "").strip(),
                        "objetivo": str(p.get("objetivo") or "").strip(),
                        "estrategias": _norm_lista(p.get("estrategias"))[:4],
                        "riesgos": _norm_lista(p.get("riesgos"))[:3],
                        "kpis": _norm_kpis(p.get("kpis")),
                        "resultados_esperados": _norm_resultados(p.get("resultados_esperados")),
                        "fases": _norm_fases(p.get("fases")),
                        "temas_consejo": _norm_lista(p.get("temas_consejo"))[:3],
                        "milestones": {a: _norm_lista(mi.get(a)) for a in _ANIOS}})
    return {
        "vision": str(d.get("vision") or "").strip(),
        "mision": str(d.get("mision") or "").strip(),
        "propuesta_valor": str(d.get("propuesta_valor") or "").strip(),
        "anio_objetivo": _norm_anio(d.get("anio_objetivo")),
        "objetivos_estrategicos": _norm_lista(d.get("objetivos_estrategicos")),
        "key_enablers": _norm_lista(d.get("key_enablers")),
        "temas_por_anio": _norm_temas(d.get("temas_por_anio")),
        "conclusion_diagnostico": str(d.get("conclusion_diagnostico") or "").strip(),
        "conclusion_entorno": str(d.get("conclusion_entorno") or "").strip(),
        "metas_3anios": metas,
        "resumen_foda": str(d.get("resumen_foda") or "").strip(),
        "resumen_entorno": str(d.get("resumen_entorno") or "").strip(),
        "pilares": pilares,
    }


def _pilares_desde_objetivos(out: dict) -> list[dict]:
    """Pilares mínimos derivados de los objetivos estratégicos (último recurso)."""
    pilares = []
    for o in (out.get("objetivos_estrategicos") or [])[:5]:
        nombre = str(o).strip()
        if not nombre:
            continue
        pilares.append({"nombre": nombre[:90], "descripcion": nombre, "razon": "",
                        "objetivo": nombre, "estrategias": [], "riesgos": [], "kpis": [],
                        "resultados_esperados": [], "fases": _norm_fases(None),
                        "temas_consejo": [], "milestones": {a: [] for a in _ANIOS}})
    return pilares
