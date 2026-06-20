"""Agente conversacional de Todd: prompt, parseo y mapeo a memory_buffer.
Lógica pura (sin red) salvo run_todd_turn (la llamada a Sonnet).
"""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry, _extract_json_object
from app.services.ai.todd import areas

_OUTPUT_SCHEMA = """{
  "message": "lo que Todd le dice al usuario (una sola pregunta o cierre)",
  "options": ["opción 1", "opción 2"] | null,
  "input": "text" | "single_choice",
  "state": {
    "company": {"name": "...", "industry": "...", "website": "...", "competitors": ["..."],
                "is_family_business": true, "employees": 0, "annual_revenue": "...", "years_operating": 0},
    "kpis": {"categoria": [{"label": "...", "current_value": 0, "benchmark": 0, "unit": "...", "alert": "..."}]},
    "vision": {"statement": "..."},
    "governance": {"score": 0, "level": "..."},
    "narrative": "resumen breve de la empresa que vas armando",
    "areas_cubiertas": ["estrategia", "..."],
    "hallazgos": {"estrategia": [{"tipo": "fortaleza|debilidad|parcial", "texto": "..."}]}
  },
  "done": false
}"""


def build_system_prompt() -> str:
    banco = "\n".join(
        f"- {a.upper()}:\n" + "\n".join(f"    · {item}" for item in items)
        for a, items in areas.AREA_BANK.items()
    )
    esenciales = "\n".join(f"  - {e}" for e in areas.ESSENTIALS)
    return (
        "Eres Todd, el secretario del consejo de Gobernia. Conduces el ONBOARDING como una "
        "ENTREVISTA conversacional, cálida y profesional, en español. Haces UNA pregunta a la vez.\n\n"
        "Tu objetivo: entender bien la empresa para un diagnóstico completo, cubriendo las 7 áreas. "
        "Tienes LIBERTAD para decidir qué preguntar: usa el banco de referencia de abajo como GUÍA "
        "(no es obligatorio preguntar todo), salta lo que no aplique o puedas inferir, y profundiza "
        "cuando una respuesta lo amerite. Cada respuesta que obtengas, clasifícala como fortaleza, "
        "debilidad o parcial en el área correspondiente (en 'hallazgos').\n\n"
        "DATOS QUE SÍ DEBES OBTENER (la plataforma los necesita):\n" + esenciales + "\n\n"
        "BANCO DE REFERENCIA POR ÁREA (guía opcional):\n" + banco + "\n\n"
        "REGLAS:\n"
        "1. Una sola pregunta por turno. Si la respuesta es acotada, ofrécela como 'single_choice' "
        "con 'options' (p. ej. Sí / Más o menos / No); si es abierta, usa 'text'.\n"
        "2. Actualiza y DEVUELVE el 'state' acumulado en cada turno (no pierdas lo ya capturado). "
        "Marca un área en 'areas_cubiertas' cuando ya la exploraste lo suficiente.\n"
        "3. No repitas lo que ya sabes. Sé natural, no un checklist frío.\n"
        "4. Pide algunos KPIs con número si el usuario los tiene; si no, regístralos cualitativos y NO insistas.\n"
        "5. Pon 'done': true SOLO cuando ya cubriste las 7 áreas y tienes los datos esenciales; en ese "
        "turno, 'message' es un cierre cálido (avisa que prepararás el diagnóstico).\n"
        "6. Responde ÚNICAMENTE con un objeto JSON válido con esta forma exacta (sin texto fuera del JSON):\n"
        + _OUTPUT_SCHEMA
    )


def build_anthropic_messages(messages: list[dict]) -> list[dict]:
    """Antepone un kickoff de usuario y mapea el transcript (todd->assistant, user->user).
    Garantiza que la lista empiece y termine en 'user' (requisito de la API)."""
    out = [{"role": "user", "content": "Conduce la entrevista de onboarding según tus reglas."}]
    for m in messages:
        role = "assistant" if m.get("role") == "todd" else "user"
        out.append({"role": role, "content": m.get("text", "")})
    return out


def parse_turn(raw: str) -> dict:
    """Normaliza la respuesta del LLM a un turno seguro. Ante basura, defaults inocuos."""
    parsed = _extract_json_object(raw) or {}
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
    }


def enforce_coverage(turn: dict) -> dict:
    """No permite cerrar (done) sin haber cubierto las 7 áreas."""
    if turn.get("done"):
        cubiertas = set((turn.get("state") or {}).get("areas_cubiertas") or [])
        if not set(areas.AREAS).issubset(cubiertas):
            turn["done"] = False
    return turn


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


def run_todd_turn(messages: list[dict]) -> dict:
    """Llamada de red: Sonnet produce el siguiente turno. Devuelve el turno parseado y con cobertura forzada.
    Sin API key → un turno determinista mínimo (para dev/tests sin red)."""
    if not settings.ANTHROPIC_API_KEY:
        return {
            "message": "Hola, soy Todd. (Modo sin IA) ¿Cómo se llama tu empresa?",
            "options": None, "input": "text", "state": {}, "done": False,
        }
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=2048,
        system=build_system_prompt(),
        messages=build_anthropic_messages(messages),
    )
    raw = response.content[0].text if response.content else ""
    return enforce_coverage(parse_turn(raw))
