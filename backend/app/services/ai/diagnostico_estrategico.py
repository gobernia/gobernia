"""Motor del Diagnóstico estratégico con investigación web (Claude + web_search).

Lógica pura (prompt, parseo, validación) separada de la llamada de red para testear sin
red ni DB. La generación corre en una task de Celery (app.tasks.diagnostico_tasks).
"""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _stream_with_retry, _create_with_retry, _extract_json_object

SECTION_KEYS = (
    "resumen_ejecutivo",
    "presencia_digital",
    "competencia",
    "tendencias_mercado",
    "contexto_economico",
    "conclusiones",
)
SECTION_TITLES = {
    "resumen_ejecutivo": "Resumen ejecutivo",
    "presencia_digital": "Presencia digital",
    "competencia": "Competencia: percibida vs. real",
    "tendencias_mercado": "Tendencias de mercado",
    "contexto_economico": "Contexto económico y regulatorio",
    "conclusiones": "Conclusiones y recomendaciones",
}

_MAX_CONTINUATIONS = 8  # tope de reanudaciones por pause_turn
_MAX_SEARCHES = 12      # presupuesto de búsquedas (suficiente para empresa + competidores + sector + economía)

SYSTEM_PROMPT = """Eres un analista estratégico senior del consejo de Gobernia.
Investigas en la web la realidad de una empresa y produces un diagnóstico estratégico
profesional, específico y accionable, en español.

ESTILO (MUY IMPORTANTE): Escribe PARA EL DUEÑO de la empresa, en lenguaje claro y directo. Ve a
los hechos, hallazgos y recomendaciones. NO narres tu método ni tus búsquedas ("busqué", "no
encontré información", "según los resultados", "con base en la información disponible", "no fue
posible determinar"), NO expliques cómo llegaste a las conclusiones ni la mecánica del análisis.
Habla de la empresa y su mercado, no de tu proceso. Si un dato no es investigable, simplemente
omítelo o conviértelo en un hallazgo de negocio (p. ej. "la marca casi no aparece en búsquedas"),
sin disculparte ni describir tu limitación.

Usa la herramienta de búsqueda web para investigar de verdad: el sitio de la empresa,
su presencia digital, sus competidores reales en su región y segmento, tendencias de su
industria y contexto económico/regulatorio de su país/región.

PRESUPUESTO DE BÚSQUEDA Y RESILIENCIA: tienes un número limitado de búsquedas. No gastes más
de 1-2 en el nombre exacto de la empresa. Si la empresa tiene poca o nula huella digital, NO
abortes ni dejes el diagnóstico vacío: regístralo como un hallazgo (presencia digital baja) y
dedica el resto de las búsquedas a lo que SÍ es investigable y valioso: los competidores que
nombró el usuario (búscalos por su nombre), las tendencias y benchmarks de la industria, y el
contexto económico/regulatorio del país. Entrega SIEMPRE un diagnóstico útil con la evidencia
que reúnas; razona desde la industria y los competidores aunque la empresa misma aparezca poco.

CRÍTICO — Competencia percibida vs. real: el usuario te dará la lista de competidores que
ÉL CREE tener. Contrástala con lo que encuentres: coincidencias, competidores reales que el
usuario omitió, y supuestos competidores que ya no lo son. Ese contraste es la sección más
valiosa.

Si recibes una AUTOEVALUACIÓN INTERNA (fortalezas/debilidades que el dueño declaró), intégrala en
tu análisis: en 'conclusiones' y en las secciones relevantes, confirma, matiza o contrasta esas
afirmaciones con lo que encuentres en la web. No te limites a repetirlas; agrégales contexto del sector.

Responde ÚNICAMENTE con un objeto JSON válido con esta forma exacta (sin texto fuera del JSON):
{
  "sections": {
    "resumen_ejecutivo": "string",
    "presencia_digital": "string",
    "competencia": "string",
    "tendencias_mercado": "string",
    "contexto_economico": "string",
    "conclusiones": "string"
  },
  "sources": [{"title": "string", "url": "string"}]
}
Cada sección: 2-4 párrafos, concreta y basada en lo que encontraste. 'sources' = las páginas
reales que consultaste."""


def _hallazgo_pairs(value) -> list[tuple[str, str]]:
    """Extrae pares (tipo, texto) de un hallazgo, tolerando TODAS las formas que el modelo
    de Todd puede producir:
      - dict {'nota'/'texto'/'detalle': str, 'tipo'/'clasificacion': str}
      - lista de dicts [{'tipo','texto'}, ...]
      - lista de strings ['...', '...']
      - string suelto '...'
    """
    def _one(v) -> tuple[str, str]:
        if isinstance(v, dict):
            tipo = str(v.get("tipo") or v.get("clasificacion") or "").strip()
            texto = str(v.get("texto") or v.get("nota") or v.get("detalle") or "").strip()
            return (tipo, texto)
        return ("", str(v or "").strip())

    if isinstance(value, dict):
        return [_one(value)]
    if isinstance(value, list):
        return [_one(v) for v in value]
    if value:
        return [_one(value)]
    return []


def _hallazgo_lineas(area: str, value) -> list[str]:
    out: list[str] = []
    for tipo, texto in _hallazgo_pairs(value):
        if not texto:
            continue
        out.append(f"  - [{area} · {tipo}] {texto}" if tipo else f"  - [{area}] {texto}")
    return out


def _normalize_hallazgos(hallazgos) -> dict:
    """Normaliza hallazgos (cualquier forma del modelo) a {area: [{'tipo','texto'}]},
    que es lo que el frontend y el FODA esperan."""
    if not isinstance(hallazgos, dict):
        return {}
    out: dict[str, list[dict]] = {}
    for area, value in hallazgos.items():
        items = [{"tipo": tipo, "texto": texto} for tipo, texto in _hallazgo_pairs(value) if texto]
        if items:
            out[str(area)] = items
    return out


def _kpis_lineas(kpis) -> list[str]:
    """Aplana los KPIs reportados (con valor) a líneas legibles. Tolera la estructura
    {categoria: [{'label','current_value','unit'}]} y variantes (valor/unidad, sueltos)."""
    if not isinstance(kpis, dict):
        return []
    out: list[str] = []
    for cat, items in kpis.items():
        lst = items if isinstance(items, list) else [items]
        for it in lst:
            if isinstance(it, dict):
                label = str(it.get("label") or it.get("nombre") or cat).strip()
                val = it.get("current_value", it.get("valor", it.get("value")))
                if val is None or it.get("unknown"):
                    continue  # sin valor → no lo inyectamos como dato duro
                unit = str(it.get("unit") or it.get("unidad") or "").strip()
                bench = it.get("benchmark")
                extra = f" (benchmark {bench}{unit})" if bench is not None else ""
                out.append(f"  - {label}: {val}{unit}{extra}".rstrip())
            elif it:
                out.append(f"  - {cat}: {str(it).strip()}")
    return out


def build_prompt(memory_buffer: dict) -> str:
    c = (memory_buffer or {}).get("company", {}) or {}
    loc = c.get("location", {}) or {}
    region = ", ".join(x for x in [loc.get("city"), loc.get("state"), loc.get("country")] if x)
    comp_raw = c.get("competitors")
    if isinstance(comp_raw, str):
        competidores = [comp_raw.strip()] if comp_raw.strip() else []
    else:
        competidores = [str(x).strip() for x in (comp_raw or []) if str(x).strip()]

    hallazgos = (memory_buffer or {}).get("hallazgos") or {}
    bloque_interno = ""
    if isinstance(hallazgos, dict) and hallazgos:
        lineas = []
        for area, items in hallazgos.items():
            lineas.extend(_hallazgo_lineas(area, items))
        if lineas:
            bloque_interno = (
                "\nAUTOEVALUACIÓN INTERNA (lo que el dueño le contó a Todd en la entrevista — "
                "fortalezas/debilidades por área). INTÉGRALA con lo que encuentres en la web "
                "(confírmala, contextualízala o matízala con datos del sector):\n"
                + "\n".join(lineas) + "\n"
            )

    kpi_lineas = _kpis_lineas((memory_buffer or {}).get("kpis"))
    bloque_kpis = ""
    if kpi_lineas:
        bloque_kpis = (
            "\nKPIs QUE LA EMPRESA REPORTÓ (con su valor actual). Tómalos en cuenta en el "
            "análisis: compáralos con benchmarks del sector y úsalos como evidencia dura:\n"
            + "\n".join(kpi_lineas) + "\n"
        )

    exito = str(((memory_buffer or {}).get("vision") or {}).get("exito_consejo") or "").strip()
    bloque_exito = ""
    if exito:
        bloque_exito = (
            "\nLO QUE EL DUEÑO ESPERA LOGRAR (su definición de éxito, con sus palabras). Orienta TODO "
            "el diagnóstico y las recomendaciones hacia esto:\n  " + exito + "\n"
        )

    return (
        f"Empresa: {c.get('name', 'N/D')}\n"
        f"Industria: {c.get('industry', 'N/D')}\n"
        f"Región donde opera: {region or 'N/D'}\n"
        f"Sitio web: {c.get('website', 'N/D')}\n"
        f"Competidores que el usuario CREE tener: {', '.join(competidores) if competidores else 'ninguno indicado'}\n"
        f"{bloque_exito}"
        f"{bloque_interno}"
        f"{bloque_kpis}\n"
        "Investiga y entrega el diagnóstico en el JSON indicado."
    )


def parse_diagnostico(raw: str) -> dict:
    """Parsea la respuesta a {sections:[{key,title,body}], sources:[{title,url}]}.
    Rellena las 6 secciones (cuerpo vacío si falta). Ante basura, secciones vacías."""
    parsed = _extract_json_object(raw) or {}
    sections_in = parsed.get("sections") or {}
    sections = [
        {"key": k, "title": SECTION_TITLES[k], "body": str(sections_in.get(k) or "").strip()}
        for k in SECTION_KEYS
    ]
    sources = []
    for s in (parsed.get("sources") or []):
        if isinstance(s, dict) and s.get("url"):
            sources.append({"title": str(s.get("title") or s["url"])[:200], "url": str(s["url"])[:500]})
    return {"sections": sections, "sources": sources[:30]}


def _diagnostico_vacio(content: dict) -> bool:
    return all(not s.get("body") for s in content.get("sections", []))


def attach_internal_findings(content: dict, memory_buffer: dict) -> dict:
    """Adjunta al content las fortalezas/debilidades que Todd recogió (memory_buffer['hallazgos'])."""
    content["fortalezas_debilidades"] = _normalize_hallazgos((memory_buffer or {}).get("hallazgos"))
    return content


_SEVERIDADES = ("alta", "media", "baja")

RIESGOS_TOOL = {
    "name": "listar_riesgos",
    "description": "Lista los riesgos operacionales y estratégicos internos derivados de las debilidades.",
    "input_schema": {
        "type": "object",
        "properties": {
            "riesgos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "riesgo": {"type": "string",
                                   "description": "El riesgo en una frase clara y directa para el dueño."},
                        "severidad": {"type": "string", "enum": list(_SEVERIDADES)},
                    },
                    "required": ["riesgo", "severidad"],
                },
            },
        },
        "required": ["riesgos"],
    },
}

_RIESGOS_SYSTEM = (
    "Eres un analista de riesgos del consejo de Gobernia. A partir de las DEBILIDADES y puntos "
    "parciales internos de una empresa, identifica los RIESGOS operacionales y estratégicos "
    "concretos que esas debilidades implican para el negocio. En español, claro y directo para el "
    "dueño, sin tecnicismos y SIN explicar tu método. 3-6 riesgos, frases cortas y accionables. "
    "Asigna severidad: alta (amenaza la continuidad/rentabilidad), media (frena el crecimiento), "
    "baja (conviene atender)."
)


def _riesgos_fallback(fortalezas_debilidades: dict) -> list[dict]:
    """Sin IA: cada debilidad/parcial interna se registra como riesgo de severidad media."""
    out = []
    for _area, items in (fortalezas_debilidades or {}).items():
        for h in (items or []):
            if str(h.get("tipo")) in ("debilidad", "parcial") and str(h.get("texto") or "").strip():
                out.append({"riesgo": str(h["texto"]).strip(), "severidad": "media"})
    return out[:6]


def derive_riesgos(memory_buffer: dict, fortalezas_debilidades: dict) -> list[dict]:
    """Deriva riesgos internos (operacionales/estratégicos) de las debilidades. Sonnet tool-use;
    sin API key o sin debilidades → fallback determinista."""
    debilidades = []
    for area, items in (fortalezas_debilidades or {}).items():
        for h in (items or []):
            if str(h.get("tipo")) in ("debilidad", "parcial") and str(h.get("texto") or "").strip():
                debilidades.append(f"[{area}] {str(h['texto']).strip()}")
    if not debilidades:
        return []
    if not settings.ANTHROPIC_API_KEY:
        return _riesgos_fallback(fortalezas_debilidades)
    c = (memory_buffer or {}).get("company") or {}
    user = (
        f"Empresa: {c.get('name', 'N/D')} · {c.get('industry', '')}\n"
        "DEBILIDADES / PUNTOS PARCIALES INTERNOS:\n" + "\n".join(f"- {d}" for d in debilidades)
        + "\n\nIdentifica los riesgos operacionales/estratégicos que estas debilidades implican."
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=120.0)
        response = _create_with_retry(
            client, model=settings.AI_MODEL, max_tokens=1024,
            system=_RIESGOS_SYSTEM, messages=[{"role": "user", "content": user}],
            tools=[RIESGOS_TOOL], tool_choice={"type": "tool", "name": "listar_riesgos"},
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        data = dict(block.input) if block and isinstance(block.input, dict) else {}
        out = []
        for r in (data.get("riesgos") or []):
            texto = str(r.get("riesgo") or "").strip()
            sev = r.get("severidad") if r.get("severidad") in _SEVERIDADES else "media"
            if texto:
                out.append({"riesgo": texto, "severidad": sev})
        return out or _riesgos_fallback(fortalezas_debilidades)
    except Exception:
        return _riesgos_fallback(fortalezas_debilidades)


def generate_diagnostico(memory_buffer: dict) -> dict:
    """Llamada de red: Opus 4.8 + web_search. Devuelve el content listo para persistir.
    Lanza RuntimeError si llega vacío/ilegible tras reintento (para marcar 'failed')."""
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("Falta ANTHROPIC_API_KEY para generar el diagnóstico.")

    # timeout generoso: Opus + varias búsquedas web puede tardar varios minutos por llamada.
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=900.0)
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": _MAX_SEARCHES}]
    user_prompt = build_prompt(memory_buffer)

    for _ in range(2):  # un reintento si llega vacío
        messages = [{"role": "user", "content": user_prompt}]
        response = None
        for _ in range(_MAX_CONTINUATIONS):
            # streaming: mantiene viva la conexión (pings) durante las búsquedas → sin APITimeoutError.
            response = _stream_with_retry(
                client,
                model=settings.DIAGNOSTICO_AI_MODEL,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
            )
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})

        raw = "\n".join(
            b.text for b in (response.content if response else []) if getattr(b, "type", None) == "text"
        )
        content = parse_diagnostico(raw)
        if not _diagnostico_vacio(content):
            content = attach_internal_findings(content, memory_buffer)
            content["riesgos"] = derive_riesgos(memory_buffer, content["fortalezas_debilidades"])
            return content

    raise RuntimeError("El diagnóstico llegó vacío o ilegible tras 2 intentos.")
