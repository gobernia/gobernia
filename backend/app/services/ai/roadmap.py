"""Genera el Roadmap Estratégico a 3 años (documento ejecutivo) desde los datos existentes.
Opus tool-use, sin web. Fallback determinista sin IA. NUNCA inventa el target numérico de las metas."""
import json
from datetime import date

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry

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
                "objetivo": {"type": "string", "description": "Objetivo estratégico del pilar (opcional)."},
                "estrategias": {"type": "array", "items": {"type": "string"},
                                "description": "0-4 estrategias principales del pilar (opcional)."},
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
    "\nCAMPOS OPCIONALES (estructura de presentación estratégica):\n"
    "- 'anio_objetivo': año horizonte del plan (año actual + 3).\n"
    "- 'objetivos_estrategicos': objetivos de alto nivel que ordenan los 3 años.\n"
    "- 'key_enablers': habilitadores transversales que hacen posible el plan (talento, tecnología, "
    "capital, gobernanza, procesos…).\n"
    "- 'temas_por_anio': el LEMA de cada año (ej. anio1 'Ordenar la casa', anio2 'Expandir el negocio', "
    "anio3 'Consolidar el liderazgo').\n"
    "- 'conclusion_diagnostico': conclusión ejecutiva del diagnóstico interno (qué nos dice, en una idea).\n"
    "- 'conclusion_entorno': conclusión estratégica de las tendencias externas (qué implican para nosotros).\n"
    "- Por pilar: 'objetivo' (su objetivo estratégico), 'estrategias' (0-4), 'kpis' (0-3, con 'label' y "
    "'actual'; 'meta' SIEMPRE VACÍO — lo fija el dueño, NUNCA inventes el número), 'resultados_esperados' "
    "(0-3, con 'titulo' corto tipo '↑ Margen bruto' y 'descripcion'), y 'fases' (el título de la fase de "
    "cada año; los pasos concretos van en 'milestones').\n"
    "\nESTA ESTRUCTURA ES UNA GUÍA, NO UN FORMULARIO: llena SOLO lo que puedas sustentar con la "
    "información dada. Si no tienes evidencia para un bloque, DÉJALO VACÍO — no inventes ni rellenes "
    "con generalidades. Un bloque vacío simplemente no se muestra; un bloque inventado destruye la "
    "credibilidad del documento.\n"
    "No inventes datos que no estén en la información dada."
)


# Cuando el Consejo ya deliberó, el Roadmap deja de ser una redacción libre: es la TRADUCCIÓN de
# esa postura a un plan de 3 años. Los pilares se derivan de las prioridades del Consejo.
_SYSTEM_CONSEJO = (
    "\n\nLA POSTURA DEL CONSEJO MANDA:\n"
    "El Consejo de Administración ya deliberó sobre esta empresa y emitió UNA conclusión, una tesis "
    "estratégica y sus prioridades (te las doy abajo). ESTE ROADMAP ES LA TRADUCCIÓN DE LO QUE EL "
    "CONSEJO DELIBERÓ, no un plan nuevo:\n"
    "- Los PILARES se DERIVAN de las prioridades del Consejo (en su orden) y de su tesis "
    "estratégica. NO inventes pilares de cero ni contradigas al Consejo.\n"
    "- La tesis estratégica del Consejo es la apuesta que el roadmap debe hacer realidad: los "
    "'objetivos_estrategicos', los 'temas_por_anio' y los milestones deben servirla.\n"
    "- Los riesgos que el Consejo señaló deben verse atendidos en algún pilar o en los "
    "'key_enablers'.\n"
    "- 'conclusion_diagnostico' debe ser fiel a la conclusión del Consejo, no una lectura distinta."
)


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
        response = _create_with_retry(
            client, model=settings.DIAGNOSTICO_AI_MODEL, max_tokens=4096,
            system=_SYSTEM + (_SYSTEM_CONSEJO if consejo else ""),
            messages=[{"role": "user", "content": user}],
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
            mi = p.get("milestones") if isinstance(p.get("milestones"), dict) else {}
            pilares.append({"nombre": str(p["nombre"]).strip(),
                            "descripcion": str(p.get("descripcion") or "").strip(),
                            "objetivo": str(p.get("objetivo") or "").strip(),
                            "estrategias": _norm_lista(p.get("estrategias"))[:4],
                            "kpis": _norm_kpis(p.get("kpis")),
                            "resultados_esperados": _norm_resultados(p.get("resultados_esperados")),
                            "fases": _norm_fases(p.get("fases")),
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
    except Exception:
        return _roadmap_fallback(memory_buffer, diagnostico_content)
