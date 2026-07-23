"""Todd, secretario del Consejo.

Un chat PERMANENTE que conoce el tablero (qué tareas hay, de quién son, cómo van),
el Roadmap y los acuerdos abiertos, y ayuda al dueño con dudas y a preparar la reunión.

Todd NO consulta la base de datos: recibe el `contexto` ya armado por el router.
Cuando el dueño dice que NO puede con una tarea, Todd usa la herramienta
`proponer_cambio_de_tarea` (task_id + motivo); el router la resuelve llamando a
`adapt_task` y devuelve la propuesta al frontend para que el dueño la confirme.

Lógica pura salvo `run_todd_secretario_turn` (la llamada a Sonnet).
"""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry

# ── Herramienta: proponer adaptar una tarea que el dueño no puede cumplir ──────
PROPONER_CAMBIO_TOOL = {
    "name": "proponer_cambio_de_tarea",
    "description": (
        "Úsala SOLO cuando el dueño dice que NO puede cumplir una tarea concreta del "
        "tablero (no tiene presupuesto/tiempo/personal, no le aplica, etc.) y conviene "
        "ofrecerle una alternativa realista. Indica el task_id EXACTO de una tarea que "
        "aparezca en el contexto y el motivo que dio el dueño, con sus palabras. "
        "NO la uses para dudas generales ni si el dueño no ha señalado una tarea puntual."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "El id EXACTO de la tarea del tablero (de las listadas en el contexto).",
            },
            "motivo": {
                "type": "string",
                "description": "El motivo por el que el dueño no puede con la tarea, en sus palabras.",
            },
            "reply": {
                "type": "string",
                "description": "Lo que Todd le dice al dueño mientras prepara la alternativa "
                               "(p. ej. «Entiendo, déjame proponerte una versión más ligera»).",
            },
        },
        "required": ["task_id", "motivo"],
    },
}


# ── Render del contexto a texto legible para el prompt ────────────────────────

def _render_tablero(tablero: dict) -> str:
    tablero = tablero or {}
    por_estado = tablero.get("por_estado") or {}
    lineas = [
        f"TABLERO ({tablero.get('total', 0)} tareas): "
        f"{por_estado.get('pendiente', 0)} pendientes, "
        f"{por_estado.get('en_progreso', 0)} en progreso, "
        f"{por_estado.get('completada', 0)} completadas."
    ]

    responsables = tablero.get("responsables") or {}
    if responsables:
        lineas.append(
            "Responsables: "
            + ", ".join(f"{owner} ({n})" for owner, n in responsables.items())
        )

    atrasadas = tablero.get("atrasadas") or []
    if atrasadas:
        lineas.append(f"\nTAREAS ATRASADAS ({len(atrasadas)}):")
        for t in atrasadas:
            lineas.append(_render_tarea(t, con_estado=False))

    tareas = tablero.get("tareas") or []
    if tareas:
        lineas.append("\nTAREAS DEL TABLERO:")
        for t in tareas:
            lineas.append(_render_tarea(t, con_estado=True))

    if not tareas and not atrasadas:
        lineas.append("El tablero todavía no tiene tareas.")
    return "\n".join(lineas)


def _render_tarea(t: dict, con_estado: bool) -> str:
    partes = [f"  - [id: {t.get('task_id', '')}] {t.get('title', '')}"]
    meta = []
    if con_estado and t.get("status"):
        meta.append(str(t["status"]))
    if t.get("owner"):
        meta.append(f"responsable: {t['owner']}")
    if t.get("priority"):
        meta.append(f"prioridad: {t['priority']}")
    if t.get("due_date"):
        meta.append(f"vence: {t['due_date']}")
    if meta:
        partes.append(" (" + ", ".join(meta) + ")")
    return "".join(partes)


def _render_roadmap(roadmap: dict) -> str:
    roadmap = roadmap or {}
    lineas = []
    if roadmap.get("vision"):
        lineas.append(f"VISIÓN: {roadmap['vision']}")
    pilares = roadmap.get("pilares") or []
    if pilares:
        lineas.append("PILARES ESTRATÉGICOS:")
        for p in pilares:
            nombre = p.get("nombre") if isinstance(p, dict) else str(p)
            obj = (p.get("objetivo") or p.get("descripcion") or "").strip() if isinstance(p, dict) else ""
            lineas.append(f"  • {nombre}" + (f" — {obj}" if obj else ""))
    return "\n".join(lineas) if lineas else "Aún no hay un Roadmap validado."


def _render_acuerdos(acuerdos: list) -> str:
    acuerdos = acuerdos or []
    if not acuerdos:
        return "No hay acuerdos abiertos del Consejo."
    lineas = [f"ACUERDOS ABIERTOS DEL CONSEJO ({len(acuerdos)}):"]
    for a in acuerdos:
        resp = a.get("responsable")
        prio = a.get("prioridad")
        extra = []
        if resp:
            extra.append(f"responsable: {resp}")
        if prio:
            extra.append(f"prioridad: {prio}")
        if a.get("pilar"):
            extra.append(f"pilar: {a['pilar']}")
        cola = f" ({', '.join(extra)})" if extra else ""
        lineas.append(f"  - {a.get('descripcion', '')}{cola}")
    return "\n".join(lineas)


def build_system_prompt(contexto: dict) -> str:
    contexto = contexto or {}
    empresa = contexto.get("empresa") or "la empresa"
    return (
        "Eres Todd, el secretario corporativo del Consejo de Gobernia. Acompañas al dueño "
        f"de {empresa} en su centro de operaciones. Eres cercano, claro y práctico: hablas en "
        "español, sin rodeos ni jerga, como un buen secretario que conoce todo lo que pasa.\n\n"
        "CONOCES EL ESTADO REAL del tablero, del Roadmap y de los acuerdos (te lo doy abajo). "
        "Responde SIEMPRE con datos concretos de ese contexto: cuántas tareas hay, cuáles están "
        "atrasadas, de quién son, qué es lo más urgente. Ayudas a preparar la reunión, a priorizar "
        "y a entender el porqué de cada cosa.\n\n"
        "REGLAS:\n"
        "1. NUNCA inventes tareas, responsables, fechas ni acuerdos que no estén en el contexto. "
        "Si algo no está, dilo con honestidad y ofrece ayudar a crearlo o revisarlo.\n"
        "2. Sé breve y útil. Si el dueño pregunta por el estado, dale el dato exacto "
        "(p. ej. «tienes 3 tareas atrasadas; la más urgente es X, de Finanzas»).\n"
        "3. Cuando el dueño diga que NO puede cumplir una tarea concreta (le falta presupuesto, "
        "tiempo, personal, o no le aplica), NO la des por perdida: usa la herramienta "
        "`proponer_cambio_de_tarea` con el task_id EXACTO de esa tarea y el motivo que te dio, "
        "para ofrecerle una alternativa realista que él pueda confirmar. Usa la herramienta solo "
        "cuando haya una tarea puntual señalada; para dudas generales, responde con texto.\n\n"
        "───────────────────────── CONTEXTO ACTUAL ─────────────────────────\n"
        + _render_tablero(contexto.get("tablero"))
        + "\n\n"
        + _render_roadmap(contexto.get("roadmap"))
        + "\n\n"
        + _render_acuerdos(contexto.get("acuerdos_abiertos"))
    )


def _to_anthropic_messages(mensajes: list[dict]) -> list[dict]:
    """Mapea el transcript a la forma de la API (todd/assistant→assistant, resto→user).
    Garantiza que empiece en 'user'."""
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


def _fallback_reply(contexto: dict) -> str:
    """Respuesta útil sin API key (dev/tests sin red): resume el tablero con los datos reales."""
    tablero = (contexto or {}).get("tablero") or {}
    por_estado = tablero.get("por_estado") or {}
    total = tablero.get("total", 0)
    atrasadas = tablero.get("atrasadas") or []
    partes = [
        f"Soy Todd, tu secretario. Ahora mismo tienes {total} tareas en el tablero "
        f"({por_estado.get('pendiente', 0)} pendientes, {por_estado.get('en_progreso', 0)} en progreso, "
        f"{por_estado.get('completada', 0)} completadas)."
    ]
    if atrasadas:
        partes.append(f"Ojo: {len(atrasadas)} están atrasadas. ¿Quieres que las repasemos?")
    else:
        partes.append("¿En qué te ayudo para preparar la reunión?")
    return " ".join(partes)


def _parse_response(response) -> dict:
    """Extrae reply + accion de la respuesta de Claude (texto y/o tool_use)."""
    reply_parts: list[str] = []
    accion = None
    for block in getattr(response, "content", []) or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            reply_parts.append(getattr(block, "text", "") or "")
        elif btype == "tool_use" and getattr(block, "name", None) == PROPONER_CAMBIO_TOOL["name"]:
            data = dict(block.input) if isinstance(getattr(block, "input", None), dict) else {}
            task_id = str(data.get("task_id") or "").strip()
            motivo = str(data.get("motivo") or "").strip()
            if task_id:
                accion = {"tipo": "proponer_cambio", "task_id": task_id, "motivo": motivo}
                tool_reply = str(data.get("reply") or "").strip()
                if tool_reply:
                    reply_parts.append(tool_reply)

    reply = "\n\n".join(p for p in reply_parts if p).strip()
    if not reply:
        reply = (
            "Déjame proponerte una alternativa para esa tarea."
            if accion
            else "Estoy aquí para ayudarte con el tablero. ¿Qué necesitas?"
        )
    return {"reply": reply, "accion": accion}


def run_todd_secretario_turn(mensajes: list[dict], contexto: dict) -> dict:
    """Un turno del chat de Todd secretario.

    `mensajes`: transcript [{role, content}] (role: user | assistant | todd).
    `contexto`: {empresa, tablero, roadmap, acuerdos_abiertos} ya armado por el router.

    Devuelve: {"reply": str, "accion": None | {"tipo": "proponer_cambio", "task_id": str, "motivo": str}}
    El router resuelve la accion (ownership + adapt_task) y le añade la `propuesta`.
    Sin API key → reply genérico útil y accion None.
    """
    if not settings.ANTHROPIC_API_KEY:
        return {"reply": _fallback_reply(contexto), "accion": None}

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=120.0)
        response = _create_with_retry(
            client,
            model=settings.AI_MODEL,
            max_tokens=1500,
            system=build_system_prompt(contexto),
            messages=_to_anthropic_messages(mensajes),
            tools=[PROPONER_CAMBIO_TOOL],
        )
        return _parse_response(response)
    except Exception:
        return {"reply": _fallback_reply(contexto), "accion": None}
