"""Todd, asistente del responsable (escritorio público /t/{token}).

Un chat scopeado SOLO a las tareas del responsable: cómo hacerlas, en qué orden,
qué significan, dudas prácticas y siguientes pasos. Sin tools, sin acciones.

Todd NO consulta la base de datos: recibe las `tareas` ya armadas por el router.
Lógica pura salvo `run_todd_responsable` (la llamada a la IA).
"""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry

_ESTADO_LABEL = {
    "pendiente": "pendiente",
    "en_progreso": "en proceso",
    "completada": "hecha",
}

_FALLBACK = (
    "Ahorita no puedo responder, intenta en un momento. Mientras, abre cada tarea "
    "y toca «¿Qué es y cómo hacerla?» para ver la guía."
)


def _render_tarea(t: dict) -> str:
    estado = _ESTADO_LABEL.get(t.get("status") or "", t.get("status") or "")
    partes = [f"  - {t.get('title', '')}"]
    meta = []
    if estado:
        meta.append(estado)
    if t.get("objetivo"):
        meta.append(f"objetivo: {t['objetivo']}")
    if meta:
        partes.append(" (" + " · ".join(meta) + ")")
    if t.get("description"):
        partes.append(f"\n    Descripción: {t['description']}")
    exp = t.get("explicacion")
    if isinstance(exp, dict):
        if exp.get("que_es"):
            partes.append(f"\n    Qué es: {exp['que_es']}")
        pasos = exp.get("como")
        if isinstance(pasos, list) and pasos:
            partes.append("\n    Cómo: " + "; ".join(str(p) for p in pasos))
    return "".join(partes)


def build_system_prompt(nombre: str | None, empresa: str | None, tareas: list[dict]) -> str:
    quien = nombre or "el responsable"
    de_empresa = f" (de {empresa})" if empresa else ""
    if tareas:
        lista = "\n".join(_render_tarea(t) for t in tareas)
    else:
        lista = "  (Todavía no tiene tareas asignadas.)"
    return (
        f"Eres Todd, el asistente de Gobernia. Estás ayudando a {quien}{de_empresa} con "
        "las tareas que le asignaron en su plan. SOLO ayudas con ESTAS tareas: cómo hacerlas, "
        "en qué orden, qué significan, dudas prácticas y siguientes pasos. Habla simple, cercano "
        "y concreto, sin tecnicismos. Si te preguntan algo que no tiene que ver con sus tareas, "
        "redirígelos con amabilidad a enfocarse en ellas. NO inventes tareas ni datos que no estén "
        "aquí.\n"
        "FORMATO: responde como en un chat de WhatsApp — texto plano, cálido y breve, en "
        "párrafos cortos. NADA de markdown: sin encabezados (#, ##), sin negritas ni asteriscos "
        "(**), sin tablas. Si necesitas enumerar pasos, usa una lista simple con guiones o "
        "números al inicio de la línea. Ve al grano; no más de 4-5 líneas salvo que pidan detalle.\n\n"
        "───────────────────────── SUS TAREAS ─────────────────────────\n"
        + lista
    )


def _to_anthropic_messages(mensajes: list[dict]) -> list[dict]:
    """Mapea el transcript a la forma de la API. Garantiza que empiece en 'user'."""
    out: list[dict] = []
    for m in mensajes or []:
        role = "assistant" if m.get("role") in ("todd", "assistant") else "user"
        content = str(m.get("content") or m.get("text") or "")
        if not content:
            continue
        out.append({"role": role, "content": content})
    if not out or out[0]["role"] != "user":
        out.insert(0, {"role": "user", "content": "Hola, Todd."})
    return out


def _parse_reply(response) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", "") or "")
    return "\n\n".join(p for p in parts if p).strip()


def run_todd_responsable(
    mensajes: list[dict],
    nombre: str | None,
    empresa: str | None,
    tareas: list[dict],
) -> str:
    """Un turno del chat de Todd para el responsable.

    `mensajes`: transcript [{role, content}] (role: user | assistant | todd).
    `tareas`: lista de {title, description, status, objetivo, explicacion(dict|None)}.

    Devuelve SOLO el texto de la respuesta. Sin API key o error → mensaje de fallback amable.
    """
    if not settings.ANTHROPIC_API_KEY:
        return _FALLBACK

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=120.0)
        response = _create_with_retry(
            client,
            model=settings.AI_MODEL,
            max_tokens=800,
            system=build_system_prompt(nombre, empresa, tareas),
            messages=_to_anthropic_messages(mensajes),
        )
        reply = _parse_reply(response)
        return reply or _FALLBACK
    except Exception:
        return _FALLBACK
