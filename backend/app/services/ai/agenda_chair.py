"""Curaduría del Chair sobre la agenda determinista (capa nodo 4).

Best-effort: sin API key, agenda vacía o cualquier fallo → devuelve la agenda determinista
intacta. Reconstrucción anti-alucinación: el Chair solo reordena y reescribe el racional de
los temas DADOS; nunca inventa temas ni evidencia.
"""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _build_company_context, _create_with_retry

_CHAIR_SYSTEM = (
    "Eres el Chair (presidente) de un consejo de administración de una empresa familiar. "
    "Recibes una agenda candidata del mes ya puntuada por un motor de señales. Tu trabajo:\n"
    "1) Decidir el ORDEN REAL de importancia del mes. Puedes subir un tema de bajo score si es "
    "estratégico (p. ej. una señal del sistema familiar) o bajar uno de score alto si es ruido "
    "estacional. Usa tu criterio de consejero, no solo el número.\n"
    "2) Reescribir el racional de cada tema en prosa breve y natural (1-2 frases), citando su "
    "evidencia, como hablaría un consejero real.\n"
    "3) Escribir una 'carta' de apertura de máximo 120 palabras que enmarque el mes con tono "
    "sobrio y directivo.\n"
    "NO inventes temas nuevos ni evidencia: trabaja SOLO con los temas dados (por su id). "
    "Responde ÚNICAMENTE con JSON válido."
)


def chair_curate_agenda(deterministic_agenda: list[dict], memory_buffer: dict, period_label: str) -> dict:
    if not settings.ANTHROPIC_API_KEY or not deterministic_agenda:
        return {"carta": "", "items": deterministic_agenda}

    company_ctx = _build_company_context(memory_buffer or {})
    items_for_llm = [
        {"id": i, "titulo": it["titulo"], "detector": it["detector"],
         "evidencia": it["evidencia"], "score": it["score"]}
        for i, it in enumerate(deterministic_agenda)
    ]
    user_prompt = (
        f"EMPRESA:\n{company_ctx}\n\n"
        f"MES: {period_label}\n\n"
        f"AGENDA CANDIDATA (ya puntuada):\n"
        f"{json.dumps(items_for_llm, ensure_ascii=False, indent=2)}\n\n"
        "Cura la agenda. Responde ÚNICAMENTE con JSON con esta forma exacta:\n"
        '{"carta": "<=120 palabras", "prioridad": [ids en orden de importancia], '
        '"racionales": {"<id>": "1-2 frases en prosa citando la evidencia"}}'
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = _create_with_retry(
            client, model=settings.AI_MODEL, max_tokens=2048,
            system=_CHAIR_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return _rebuild(deterministic_agenda, response.content[0].text)
    except Exception:
        return {"carta": "", "items": deterministic_agenda}


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("respuesta sin JSON")
    return text[start:end + 1]


def _rebuild(deterministic_agenda: list[dict], raw_text: str) -> dict:
    parsed = json.loads(_extract_json(raw_text))
    carta = str(parsed.get("carta") or "")
    racionales = parsed.get("racionales") or {}
    prioridad = parsed.get("prioridad") or []

    n = len(deterministic_agenda)
    seen: set = set()
    orden_final: list = []
    for pid in prioridad:
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            continue
        if 0 <= pid < n and pid not in seen:
            seen.add(pid)
            orden_final.append(pid)
    for i in range(n):  # anexa los faltantes en su orden original
        if i not in seen:
            orden_final.append(i)

    items: list = []
    for pos, pid in enumerate(orden_final, start=1):
        original = dict(deterministic_agenda[pid])
        original["orden"] = pos
        nuevo = racionales.get(str(pid))
        if nuevo:
            original["racional"] = str(nuevo)
        items.append(original)
    return {"carta": carta, "items": items}
