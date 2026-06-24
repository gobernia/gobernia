"""Adapta una tarea a la realidad del usuario: analiza su comentario en texto libre
(p. ej. «no tengo presupuesto para un despacho») y propone una alternativa realista.
Lógica pura salvo la llamada a Sonnet (salida estructurada por tool use)."""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry

ADAPTAR_TOOL = {
    "name": "proponer_alternativa",
    "description": "Propone una tarea alternativa, realista para la situación que describe el usuario.",
    "input_schema": {
        "type": "object",
        "properties": {
            "nueva_tarea": {"type": "string",
                            "description": "Título corto y accionable de la tarea alternativa."},
            "descripcion": {"type": "string", "description": "1-2 oraciones de en qué consiste."},
            "por_que": {"type": "string",
                        "description": "Por qué encaja mejor con lo que dijo el usuario (su limitación)."},
        },
        "required": ["nueva_tarea", "descripcion", "por_que"],
    },
}


def parse_adaptacion(d: dict, fallback_titulo: str = "") -> dict:
    d = d or {}
    return {
        "nueva_tarea": str(d.get("nueva_tarea") or fallback_titulo).strip(),
        "descripcion": str(d.get("descripcion") or "").strip(),
        "por_que": str(d.get("por_que") or "").strip(),
    }


def adapt_task(task_title: str, objetivo: str, empresa_ctx: str, feedback: str) -> dict:
    """Propone una alternativa con Sonnet (tool use). Sin API key → eco de la tarea actual."""
    if not settings.ANTHROPIC_API_KEY:
        return parse_adaptacion({}, fallback_titulo=task_title)
    system = (
        "Eres Todd, secretario del consejo de Gobernia. El dueño de una empresa te dice por qué NO "
        "puede hacer una tarea de su plan (por ejemplo: no tiene presupuesto, no tiene tiempo, no le "
        "aplica, le falta personal). Analiza su comentario en español y propón UNA tarea ALTERNATIVA "
        "que persiga un objetivo parecido pero sea REALISTA para su situación: si el problema es "
        "dinero, propón una opción de mucho menor costo (gratis o casi); si es tiempo o personal, algo "
        "más ligero o por etapas. Debe ser concreta y accionable. Si el comentario no da un motivo "
        "claro, propón una versión más simple y económica de la misma tarea. No inventes cifras."
    )
    user = (
        f"EMPRESA: {empresa_ctx or 'N/D'}\n"
        f"OBJETIVO DEL MES: {objetivo or 'N/D'}\n"
        f"TAREA ACTUAL (que el usuario no puede hacer): {task_title}\n"
        f"LO QUE DICE EL USUARIO: {feedback or '(sin detalle)'}"
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=120.0)
        response = _create_with_retry(
            client, model=settings.AI_MODEL, max_tokens=1024, system=system,
            messages=[{"role": "user", "content": user}],
            tools=[ADAPTAR_TOOL], tool_choice={"type": "tool", "name": "proponer_alternativa"},
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        return parse_adaptacion(dict(block.input) if block and isinstance(block.input, dict) else {},
                                fallback_titulo=task_title)
    except Exception:
        return parse_adaptacion({}, fallback_titulo=task_title)
