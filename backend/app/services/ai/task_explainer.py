"""Explicación de una tarea, generada bajo demanda (qué es / cómo / tiempo / dificultad)."""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry
from app.services.ai.modelos import ajustes_ai, pedir_herramienta

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


def explicacion_visible(e) -> dict | None:
    """La explicación ("¿Qué es y cómo hacerla?") solo si de verdad existe. El mismo campo guarda
    también el "¿Qué subo?" (clave "evidencia"), que por sí solo no es una explicación."""
    return e if isinstance(e, dict) and str(e.get("que_es") or "").strip() else None


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
        response = pedir_herramienta(
            _create_with_retry, client, model=settings.AI_MODEL, max_tokens=1024, system=system,
            messages=[{"role": "user", "content": user}],
            tool=EXPLICACION_TOOL, **ajustes_ai(en_vivo=True),
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        return parse_explicacion(dict(block.input) if block and isinstance(block.input, dict) else {})
    except Exception:
        return parse_explicacion({"que_es": task_title, "como": []})


# ── "¿Qué subo?": qué documento sirve de evidencia para la tarea ─────────────────────────────
# Pedido del dueño de Gobernia (25 nov 2026): alguien sin experiencia no sabe qué subir. Se dice
# qué pidió el Consejo, otras opciones que una empresa mediana sí tiene y, si no hay documento,
# que le cuente a Todd qué hicieron.

QUE_SUBIR_TOOL = {
    "name": "que_subir",
    "description": "Dice qué documento subir como evidencia de una tarea, explicado para alguien sin experiencia.",
    "input_schema": {
        "type": "object",
        "properties": {
            "pide": {"type": "string", "description": (
                "El documento principal que demuestra que la tarea se hizo, en 1 o 2 oraciones cortas y "
                "sencillas. Si el Consejo ya pidió uno, explícalo; si no, propón el más natural.")},
            "alternativas": {"type": "array", "items": {"type": "string"}, "description": (
                "2 o 3 documentos alternativos que una empresa mediana normalmente SÍ tiene o puede "
                "sacar en poco tiempo (reporte del sistema contable, estados de cuenta, un correo con el "
                "acuerdo, una foto, una tabla sencilla en Excel…). Cada uno en una línea corta.")},
            "sin_documento": {"type": "string", "description": (
                "Si no tiene ningún documento: qué contarle a Todd, en una oración corta (qué se hizo, "
                "cuándo, quién y con qué resultado concreto).")},
        },
        "required": ["pide", "alternativas", "sin_documento"],
    },
}


def parse_que_subir(d: dict, required_doc: str | None = None) -> dict:
    d = d or {}
    alternativas = d.get("alternativas") if isinstance(d.get("alternativas"), list) else []
    return {
        "pide": str(d.get("pide") or required_doc or "Un documento que muestre que la tarea se hizo.").strip(),
        "alternativas": [str(a).strip() for a in alternativas if str(a).strip()][:3],
        "sin_documento": str(d.get("sin_documento") or (
            "Cuéntale a Todd qué se hizo, cuándo, quién participó y con qué resultado.")).strip(),
    }


def generate_que_subir(task_title: str, description: str | None, objetivo: str, empresa: str,
                       required_doc: str | None) -> dict:
    """Sonnet (en vivo: alguien espera la respuesta). Sin API key o si falla → lo que pidió el Consejo."""
    if not settings.ANTHROPIC_API_KEY:
        return parse_que_subir({}, required_doc)
    system = (
        "Eres Todd, secretario del consejo de Gobernia. Le explicas a alguien SIN experiencia qué "
        "documento subir como evidencia de una tarea, en español sencillo, sin tecnicismos. Sé realista: "
        "la gente sube lo que tiene; propone documentos que una empresa mediana mexicana sí tiene o puede "
        "sacar rápido. No inventes datos de la empresa."
    )
    user = (
        f"EMPRESA: {empresa or 'N/D'}\n"
        f"OBJETIVO: {objetivo or 'N/D'}\n"
        f"TAREA: {task_title}\n"
        + (f"DESCRIPCIÓN: {description}\n" if description else "")
        + (f"DOCUMENTO QUE PIDIÓ EL CONSEJO: {required_doc}\n" if required_doc else "")
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=120.0)
        response = pedir_herramienta(
            _create_with_retry, client, model=settings.AI_MODEL, max_tokens=700, system=system,
            messages=[{"role": "user", "content": user}],
            tool=QUE_SUBIR_TOOL, **ajustes_ai(en_vivo=True),
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        return parse_que_subir(dict(block.input) if block and isinstance(block.input, dict) else {}, required_doc)
    except Exception:
        return parse_que_subir({}, required_doc)
