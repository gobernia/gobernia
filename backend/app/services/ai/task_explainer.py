"""Explicación de una tarea, generada bajo demanda (qué es / cómo / tiempo / dificultad)."""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry

_DIFS = ("Fácil", "Media", "Difícil")

EXPLICACION_TOOL = {
    "name": "explicar_tarea",
    "description": "Explica una tarea del plan para que el dueño la entienda y la ejecute.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tiempo": {"type": "string", "description": "Estimado, p. ej. '~2 h', '1 día'."},
            "dificultad": {"type": "string", "enum": list(_DIFS)},
            "que_es": {"type": "string", "description": "Qué es la tarea, claro y sin tecnicismos."},
            "como": {"type": "array", "items": {"type": "string"}, "description": "Pasos concretos."},
        },
        "required": ["tiempo", "dificultad", "que_es", "como"],
    },
}


def parse_explicacion(d: dict) -> dict:
    d = d or {}
    dif = d.get("dificultad") if d.get("dificultad") in _DIFS else "Media"
    como = d.get("como")
    como = [str(x) for x in como if str(x).strip()] if isinstance(como, list) else []
    return {
        "tiempo": str(d.get("tiempo") or "~1 h"),
        "dificultad": dif,
        "que_es": str(d.get("que_es") or ""),
        "como": como,
    }


def generate_explicacion(task_title: str, objetivo: str, empresa: str, kpi: str | None) -> dict:
    """Genera la explicación con Sonnet (tool use). Sin API key → explicación mínima."""
    if not settings.ANTHROPIC_API_KEY:
        return parse_explicacion({"que_es": task_title, "como": []})
    system = (
        "Eres Todd, secretario del consejo de Gobernia. Explica UNA tarea del plan al dueño de una "
        "empresa para que la entienda y la ejecute, en español, claro y sin tecnicismos. 'que_es': 2-4 "
        "oraciones de qué es y por qué importa. 'como': 3-5 pasos concretos y accionables. 'tiempo' y "
        "'dificultad' realistas. No inventes datos específicos que no tengas."
    )
    user = (
        f"EMPRESA: {empresa or 'N/D'}\n"
        f"OBJETIVO DEL MES: {objetivo or 'N/D'}\n"
        f"KPI relacionado: {kpi or 'N/D'}\n"
        f"TAREA: {task_title}"
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=120.0)
        response = _create_with_retry(
            client, model=settings.AI_MODEL, max_tokens=1024, system=system,
            messages=[{"role": "user", "content": user}],
            tools=[EXPLICACION_TOOL], tool_choice={"type": "tool", "name": "explicar_tarea"},
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        return parse_explicacion(dict(block.input) if block and isinstance(block.input, dict) else {})
    except Exception:
        return parse_explicacion({"que_es": task_title, "como": []})
