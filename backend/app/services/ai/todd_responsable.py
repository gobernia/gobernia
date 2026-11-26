"""Todd, asistente del responsable (escritorio público /t/{token}).

Un chat scopeado SOLO a las tareas del responsable: cómo hacerlas, en qué orden,
qué significan, dudas prácticas y siguientes pasos. Una sola acción: guardar en una tarea lo
que hicieron cuando no hay documento (registrar_avance).

Todd NO consulta la base de datos: recibe las `tareas` ya armadas por el router.
Lógica pura salvo `run_todd_responsable` (la llamada a la IA).
"""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry, sistema_con_cache
from app.services.ai.modelos import ajustes_ai, pedir_texto
from app.services.ai.avance_herramienta import REGISTRAR_AVANCE_TOOL

_ESTADO_LABEL = {
    "pendiente": "pendiente",
    "en_progreso": "en proceso",
    "completada": "hecha",
}

_VEREDICTO = {
    "validada": "validado", "parcial": "avance parcial", "insuficiente": "falta sustento",
    "revisando": "lo está leyendo", "sin_revisar": "sin revisar",
}

_FALLBACK = (
    "Ahorita no puedo responder, intenta en un momento. Mientras, abre cada tarea "
    "y toca «¿Qué es y cómo hacerla?» para ver la guía."
)


def _render_tarea(t: dict) -> str:
    estado = _ESTADO_LABEL.get(t.get("status") or "", t.get("status") or "")
    partes = [f"  - [id: {t['task_id']}] {t.get('title', '')}" if t.get("task_id") else f"  - {t.get('title', '')}"]
    meta = []
    if estado:
        meta.append(estado)
    if t.get("objetivo"):
        meta.append(f"objetivo: {t['objetivo']}")
    if meta:
        partes.append(" (" + " · ".join(meta) + ")")
    if t.get("description"):
        partes.append(f"\n    Descripción: {t['description']}")
    v = t.get("validacion") if isinstance(t.get("validacion"), dict) else None
    n = int(t.get("evidencias") or 0)
    if n or v:
        partes.append(f"\n    Evidencia: {n} documento(s)")
        if v and v.get("estado"):
            partes.append(f"; el Auditor dice: {_VEREDICTO.get(v['estado'], v['estado'])}")
            if v.get("documento"):
                partes.append(f" (es {v['documento']})")
            if v.get("falta"):
                partes.append(f"; falta: {v['falta']}")
            if v.get("alternativas"):
                partes.append("; también serviría: " + " / ".join(v["alternativas"]))
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
        "números al inicio de la línea. Ve al grano; no más de 4-5 líneas salvo que pidan detalle.\n"
        "CÓMO SE USA SU PÁGINA: en cada tarea, «¿Qué es y cómo hacerla?» abre la explicación, y en "
        "la sección «Evidencia» el botón «Subir documento» sube el documento que demuestra el avance "
        "(PDF, imagen, Excel, Word o PowerPoint, hasta 10 MB). El Auditor lo revisa al momento y ahí "
        "mismo dice qué está, qué falta y qué otra cosa también sirve. Desde su página NO puede "
        "cambiar el estado de la tarea ni borrar documentos: eso lo hace el dueño de la empresa, "
        "así que para eso, o para cualquier cosa que no se pueda hacer aquí, que lo vea con quien "
        "le asignó la tarea. No inventes botones ni pasos.\n"
        "SI NO TIENE DOCUMENTO: que no suba cualquier cosa. Pregúntale qué hicieron (qué se hizo, "
        "cuándo, quién participó y con qué resultado concreto: cifras, nombres, fechas) en una o dos "
        "preguntas cortas. Cuando ya lo sepas, usa la herramienta `registrar_avance` con el id EXACTO "
        "de su tarea y con sus palabras, sin inventar nada: queda guardado en la tarea y el Auditor lo "
        "revisa. Nunca le muestres los ids.\n\n"
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
) -> dict:
    """Un turno del chat de Todd para el responsable.

    `mensajes`: transcript [{role, content}] (role: user | assistant | todd).
    `tareas`: lista de {task_id, title, description, status, objetivo, explicacion, evidencias, validacion}.

    Devuelve {"reply": str, "avance": dict | None}. `avance` trae lo que Todd decidió guardar con
    `registrar_avance` (el router lo convierte en el PDF de la tarea). Sin API key o error →
    mensaje de respaldo amable y sin avance.
    """
    if not settings.ANTHROPIC_API_KEY:
        return {"reply": _FALLBACK, "avance": None}

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=120.0)
        response = pedir_texto(
            _create_with_retry, client,
            model=settings.AI_MODEL,
            max_tokens=800,
            system=sistema_con_cache(build_system_prompt(nombre, empresa, tareas)),
            messages=_to_anthropic_messages(mensajes),
            tools=[REGISTRAR_AVANCE_TOOL],
            **ajustes_ai(en_vivo=True),
        )
        avance = next((dict(b.input) for b in (getattr(response, "content", None) or [])
                       if getattr(b, "type", None) == "tool_use"
                       and getattr(b, "name", None) == REGISTRAR_AVANCE_TOOL["name"]
                       and isinstance(getattr(b, "input", None), dict)), None)
        reply = _parse_reply(response)
        if not reply and not avance:
            reply = _FALLBACK
        return {"reply": reply, "avance": avance}
    except Exception:
        return {"reply": _FALLBACK, "avance": None}
