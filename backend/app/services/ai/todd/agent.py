"""Agente conversacional de Todd: prompt, parseo y mapeo a memory_buffer.
Lógica pura (sin red) salvo run_todd_turn (la llamada a Sonnet, con salida estructurada por tool use).
"""
import json
import unicodedata

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry, _extract_json_object
from app.services.ai.todd import areas

# El modelo a veces marca las áreas con etiquetas libres ("Recursos Humanos", "Financiera",
# "Operaciones", con acentos/mayúsculas). Las mapeamos a las 7 claves canónicas para que la
# comprobación de cobertura no atrape al usuario en un bucle de cierre.
_AREA_ALIASES = {
    "estrategia": "estrategia", "estrategico": "estrategia", "estrategica": "estrategia",
    "comercial": "comercial", "ventas": "comercial", "mercado": "comercial",
    "marketing": "comercial", "comercializacion": "comercial",
    "operativo": "operativo", "operativa": "operativo", "operaciones": "operativo",
    "operacion": "operativo", "operacional": "operativo",
    "rh": "rh", "rrhh": "rh", "recursos humanos": "rh", "recurso humano": "rh",
    "capital humano": "rh", "personal": "rh", "talento": "rh", "gente": "rh",
    "financiero": "financiero", "financiera": "financiero", "finanzas": "financiero",
    "financiamiento": "financiero", "financieros": "financiero",
    "legal": "legal", "juridico": "legal", "fiscal": "legal", "cumplimiento": "legal",
    "familiar": "familiar", "familia": "familiar", "sucesion": "familiar", "familiares": "familiar",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _canon_token(raw: str, canon_keys: list[str], aliases: dict[str, str] | None) -> str | None:
    """Mapea una etiqueta libre a una de `canon_keys`, sin acentos ni mayúsculas.
    Orden: alias exacto → clave canónica (exacta o contenida) → alias contenido."""
    key = _strip_accents(str(raw)).lower().strip()
    if not key:
        return None
    if aliases and key in aliases:
        return aliases[key]
    for ck in canon_keys:
        cks = _strip_accents(ck).lower()
        if key == cks or cks in key:
            return ck
    if aliases:
        for alias, canon in aliases.items():
            if alias in key:
                return canon
    return None


def _normalize_areas(value, canon_keys: list[str], aliases: dict[str, str] | None = None) -> list[str]:
    """Normaliza una lista de etiquetas a claves canónicas únicas, en el orden de `canon_keys`."""
    if not isinstance(value, list):
        return []
    found = {_canon_token(v, canon_keys, aliases) for v in value}
    found.discard(None)
    return [k for k in canon_keys if k in found]

# Tool que FUERZA la salida estructurada (garantiza JSON válido, sin prosa suelta).
RESPONSE_TOOL = {
    "name": "responder_turno",
    "description": "Responde el siguiente turno de la entrevista de onboarding de Todd.",
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {"type": "string",
                        "description": "Lo que Todd le dice al usuario: UNA pregunta concreta, o el cierre."},
            "options": {"type": "array", "items": {"type": "string"},
                        "description": "2-4 opciones de selección simple; vacío si la respuesta es abierta."},
            "input": {"type": "string", "enum": ["text", "single_choice"]},
            "state": {"type": "object",
                      "description": "Estado acumulado COMPLETO y actualizado: company, kpis, vision, "
                                     "governance, narrative, areas_cubiertas, hallazgos."},
            "done": {"type": "boolean"},
            "reanudar_desde": {"type": "string", "enum": ["continuar", "rehacer"],
                               "description": "Solo al editar: 'continuar' si la corrección no invalida "
                                              "respuestas posteriores, 'rehacer' si sí."},
        },
        "required": ["message", "input", "state", "done"],
    },
}


def build_system_prompt(state: dict | None = None) -> str:
    banco = "\n".join(
        f"- {a.upper()}:\n" + "\n".join(f"    · {item}" for item in items)
        for a, items in areas.AREA_BANK.items()
    )
    esenciales = "\n".join(f"  - {e}" for e in areas.ESSENTIALS)
    estado_txt = ""
    if state:
        estado_txt = (
            "\n\nESTADO ACUMULADO ACTUAL (constrúyelo encima, NO lo pierdas; úsalo para saber qué ya "
            "preguntaste y qué áreas faltan por cubrir):\n" + json.dumps(state, ensure_ascii=False)
        )
    return (
        "Eres Todd, el secretario del consejo de Gobernia. Conduces el ONBOARDING como una "
        "ENTREVISTA conversacional, cálida y profesional, en español. Haces UNA pregunta a la vez.\n\n"
        "Tu objetivo: entender bien la empresa para un diagnóstico completo, cubriendo las 7 áreas. "
        "Tienes LIBERTAD para decidir qué preguntar: usa el banco de referencia de abajo como GUÍA "
        "(no es obligatorio preguntar todo), salta lo que no aplique o puedas inferir, y profundiza "
        "cuando una respuesta lo amerite.\n\n"
        "DATOS QUE SÍ DEBES OBTENER (la plataforma los necesita):\n" + esenciales + "\n\n"
        "BANCO DE REFERENCIA POR ÁREA (guía opcional — úsalas como preguntas concretas):\n" + banco + "\n\n"
        "REGLAS:\n"
        "1. Haz preguntas CONCRETAS y ESPECÍFICAS, una a la vez, sobre un solo punto. Usa las "
        "afirmaciones del banco como preguntas directas (p. ej. «¿Tienen un tablero de indicadores "
        "para monitorear sus objetivos?»). NUNCA hagas preguntas vagas como «cuéntame más sobre tu empresa».\n"
        "2. Cuando la respuesta sea acotada, ofrécela como 'single_choice' con 'options' "
        "(p. ej. [\"Sí\", \"Más o menos\", \"No\"]); si es abierta, usa 'text' y deja 'options' vacío.\n"
        "3. NUNCA repitas una pregunta que ya hiciste. Si el usuario responde con otra pregunta "
        "(p. ej. «¿qué quieres saber?») o algo ambiguo, NO te quedes en blanco: haz directamente la "
        "siguiente pregunta específica que falte por cubrir.\n"
        "4. Mantén y DEVUELVE el 'state' COMPLETO y actualizado en cada turno. Marca cada área en "
        "'areas_cubiertas' usando EXACTAMENTE estas 7 claves en minúscula: "
        "estrategia, comercial, operativo, rh, financiero, legal, familiar (NO uses etiquetas largas "
        "como «Recursos Humanos»). Clasifica lo que aprendas como fortaleza, debilidad o parcial en "
        "'hallazgos' por área.\n"
        "5. Pide algunos KPIs con número si el usuario los tiene; si no, regístralos cualitativos y NO insistas.\n"
        "6. Pon 'done': true SOLO cuando ya cubriste las 7 áreas y tienes los datos esenciales; en ese "
        "turno, 'message' es un cierre cálido (avisa que prepararás el diagnóstico)."
        + estado_txt
    )


def build_anthropic_messages(messages: list[dict]) -> list[dict]:
    """Antepone un kickoff de usuario y mapea el transcript (todd->assistant, user->user).
    Garantiza que la lista empiece en 'user' (requisito de la API)."""
    out = [{"role": "user", "content": "Conduce la entrevista de onboarding según tus reglas."}]
    for m in messages:
        role = "assistant" if m.get("role") == "todd" else "user"
        out.append({"role": role, "content": m.get("text", "")})
    return out


def _normalize_turn(parsed: dict) -> dict:
    """Normaliza un turno (dict ya parseado) a la forma segura. Ante datos faltantes, defaults inocuos."""
    parsed = parsed or {}
    state = parsed.get("state")
    if not isinstance(state, dict):
        state = {}
    options = parsed.get("options")
    if not (isinstance(options, list) and options):
        options = None
    input_type = parsed.get("input")
    if input_type not in ("text", "single_choice"):
        input_type = "single_choice" if options else "text"
    return {
        "message": str(parsed.get("message") or "¿Podrías contarme un poco más sobre tu empresa?"),
        "options": [str(o) for o in options] if options else None,
        "input": input_type,
        "state": state,
        "done": bool(parsed.get("done")),
        "reanudar_desde": parsed.get("reanudar_desde") if parsed.get("reanudar_desde") in ("continuar", "rehacer") else "continuar",
    }


def parse_turn(raw: str) -> dict:
    """Normaliza la respuesta del LLM (texto JSON) a un turno seguro. Ante basura, defaults inocuos."""
    return _normalize_turn(_extract_json_object(raw) or {})


def enforce_coverage_against(turn: dict, required: list[str],
                             aliases: dict[str, str] | None = None) -> dict:
    """No permite cerrar (done) sin cubrir todas las áreas/categorías de `required`.
    Normaliza las áreas marcadas a claves canónicas (tolera etiquetas libres del modelo:
    acentos, mayúsculas, sinónimos), evitando el bucle de cierre."""
    state = turn.get("state")
    if isinstance(state, dict):
        state["areas_cubiertas"] = _normalize_areas(state.get("areas_cubiertas"), required, aliases)
    if turn.get("done"):
        cubiertas = set((turn.get("state") or {}).get("areas_cubiertas") or [])
        if not set(required).issubset(cubiertas):
            turn["done"] = False
    return turn


def enforce_coverage(turn: dict) -> dict:
    """No permite cerrar sin las 7 áreas internas (tolerando etiquetas libres del modelo)."""
    return enforce_coverage_against(turn, areas.AREAS, _AREA_ALIASES)


def state_to_memory_buffer(state: dict) -> dict:
    """Mapea el estado de Todd a la estructura de memory_buffer que la app ya consume."""
    state = state or {}
    return {
        "company": state.get("company") or {},
        "kpis": state.get("kpis") or {},
        "vision": state.get("vision") or {},
        "governance": state.get("governance") or {},
        "ai_context": {"company_narrative": str(state.get("narrative") or "")},
        "hallazgos": state.get("hallazgos") or {},
    }


def run_todd_turn(messages: list[dict], state: dict | None = None) -> dict:
    """Llamada de red: Sonnet produce el siguiente turno con salida ESTRUCTURADA (tool use forzado),
    así que siempre devuelve un objeto válido (nunca prosa suelta). Devuelve el turno normalizado y
    con cobertura forzada. Sin API key → un turno determinista mínimo (dev/tests sin red)."""
    if not settings.ANTHROPIC_API_KEY:
        return {
            "message": "Hola, soy Todd. (Modo sin IA) ¿Cómo se llama tu empresa?",
            "options": None, "input": "text", "state": {}, "done": False,
        }
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=4096,
        system=build_system_prompt(state),
        messages=build_anthropic_messages(messages),
        tools=[RESPONSE_TOOL],
        tool_choice={"type": "tool", "name": "responder_turno"},
    )
    block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    parsed = dict(block.input) if block is not None and isinstance(block.input, dict) else {}
    return enforce_coverage(_normalize_turn(parsed))


def _edit_note(edited_question: str, new_answer: str) -> str:
    return (
        "\n\nEDICIÓN: el usuario acaba de CORREGIR una respuesta anterior. "
        f"A la pregunta «{edited_question}» ahora responde: «{new_answer}». "
        "Revisa las respuestas que dio DESPUÉS de esa pregunta y decide 'reanudar_desde':\n"
        "- 'continuar' si la corrección NO invalida ninguna respuesta posterior → incorpóralas al "
        "state y haz la SIGUIENTE pregunta que falte (no repitas lo ya respondido).\n"
        "- 'rehacer' si la corrección invalida alguna respuesta posterior → en 'message' avisa breve "
        "(p. ej. «Con ese cambio, repasemos un par de cosas desde aquí») y vuelve a preguntar lo que sigue."
    )


def run_todd_edit(messages: list[dict], edited_question: str, new_answer: str,
                  state: dict | None = None) -> dict:
    """Tras una corrección: Todd ve el transcript ya corregido + una nota de edición, y decide
    'reanudar_desde' (continuar/rehacer) además del siguiente turno. Sin API key → rehacer mínimo."""
    if not settings.ANTHROPIC_API_KEY:
        return {"message": "Listo, lo dejé corregido. Continuemos.", "options": None,
                "input": "text", "state": state or {}, "done": False, "reanudar_desde": "rehacer"}
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=4096,
        system=build_system_prompt(state) + _edit_note(edited_question, new_answer),
        messages=build_anthropic_messages(messages),
        tools=[RESPONSE_TOOL],
        tool_choice={"type": "tool", "name": "responder_turno"},
    )
    block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    parsed = dict(block.input) if block is not None and isinstance(block.input, dict) else {}
    return enforce_coverage(_normalize_turn(parsed))
