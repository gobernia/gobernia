"""Motor del Diagnóstico estratégico con investigación web (Claude + web_search).

Lógica pura (prompt, parseo, validación) separada de la llamada de red para testear sin
red ni DB. La generación corre en una task de Celery (app.tasks.diagnostico_tasks).
"""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _stream_with_retry, _extract_json_object

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


def build_prompt(memory_buffer: dict) -> str:
    c = (memory_buffer or {}).get("company", {}) or {}
    loc = c.get("location", {}) or {}
    region = ", ".join(x for x in [loc.get("city"), loc.get("state"), loc.get("country")] if x)
    competidores = c.get("competitors") or []
    return (
        f"Empresa: {c.get('name', 'N/D')}\n"
        f"Industria: {c.get('industry', 'N/D')}\n"
        f"Región donde opera: {region or 'N/D'}\n"
        f"Sitio web: {c.get('website', 'N/D')}\n"
        f"Competidores que el usuario CREE tener: {', '.join(competidores) if competidores else 'ninguno indicado'}\n\n"
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
            return content

    raise RuntimeError("El diagnóstico llegó vacío o ilegible tras 2 intentos.")
