"""Genera la Minuta del consejo (nodo 5, V1 single-pass). Best-effort con fallback determinista.

Reconstrucción anti-alucinación: los temas se anclan a la agenda dada (titulo); el Chair solo
añade síntesis + decisión binaria. Nunca inventa temas.
"""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _build_company_context, _create_with_retry

_MAX_TEMAS = 5
_DEF_PREGUNTA = "¿Cómo proceder con: {titulo}?"
_DEF_A = "Tomar acción este mes."
_DEF_B = "Aplazar y monitorear."

_MINUTA_SYSTEM = (
    "Eres el Chair (presidente) de un consejo de administración de una empresa familiar, "
    "presidiendo la sesión mensual. Recibes la agenda priorizada del mes. Por cada tema:\n"
    "1) Escribe una 'sintesis' breve (1-2 frases) de la deliberación del consejo sobre el tema.\n"
    "2) Plantea una 'decision' binaria que el dueño debe cerrar: una 'pregunta' clara y dos "
    "opciones concretas y accionables ('opcion_a' y 'opcion_b'), cada una una acción específica.\n"
    "Además escribe una 'carta' de apertura de máximo 120 palabras, sobria y directiva.\n"
    "NO inventes temas nuevos: trabaja SOLO con los temas dados (por su id). "
    "Responde ÚNICAMENTE con JSON válido."
)


def generate_minuta(agenda_items: list[dict], memory_buffer: dict, period_label: str) -> dict:
    items = (agenda_items or [])[:_MAX_TEMAS]
    if not items:
        return {"carta": "", "temas": []}
    if not settings.ANTHROPIC_API_KEY:
        return {"carta": "", "temas": _rebuild_minuta(items, {})}

    company_ctx = _build_company_context(memory_buffer or {})
    items_for_llm = [
        {"id": i, "titulo": it["titulo"], "evidencia": it.get("evidencia", []),
         "racional": it.get("racional", "")}
        for i, it in enumerate(items)
    ]
    user_prompt = (
        f"EMPRESA:\n{company_ctx}\n\n"
        f"MES: {period_label}\n\n"
        f"AGENDA DEL MES:\n{json.dumps(items_for_llm, ensure_ascii=False, indent=2)}\n\n"
        "Sesiona el consejo. Responde ÚNICAMENTE con JSON con esta forma exacta:\n"
        '{"carta": "<=120 palabras", "temas": {"<id>": '
        '{"sintesis": "...", "pregunta": "...", "opcion_a": "...", "opcion_b": "..."}}}'
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = _create_with_retry(
            client, model=settings.AI_MODEL, max_tokens=2048,
            system=_MINUTA_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        parsed = json.loads(_extract_json(response.content[0].text))
        carta = str(parsed.get("carta") or "")
        temas_llm = parsed.get("temas") or {}
        return {"carta": carta, "temas": _rebuild_minuta(items, temas_llm)}
    except Exception:
        return {"carta": "", "temas": _rebuild_minuta(items, {})}


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("respuesta sin JSON")
    return text[start:end + 1]


def _rebuild_minuta(items: list[dict], temas_llm: dict) -> list[dict]:
    temas: list[dict] = []
    for i, it in enumerate(items):
        llm = temas_llm.get(str(i)) or {}
        titulo = it["titulo"]
        temas.append({
            "id": i,
            "titulo": titulo,
            "sintesis": str(llm.get("sintesis") or it.get("racional") or ""),
            "decision": {
                "pregunta": str(llm.get("pregunta") or _DEF_PREGUNTA.format(titulo=titulo)),
                "opcion_a": str(llm.get("opcion_a") or _DEF_A),
                "opcion_b": str(llm.get("opcion_b") or _DEF_B),
                "decision_tomada": None,
            },
            "compromiso": None,
        })
    return temas
