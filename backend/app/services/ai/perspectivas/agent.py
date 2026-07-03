"""Motor de entrevista de perspectivas: prompt por rol + turno estructurado (tool use).
Reutiliza el tool-use de Todd; NO exige cobertura de 7 áreas (es específico por rol)."""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry
from app.services.ai.todd.agent import RESPONSE_TOOL, build_anthropic_messages, _normalize_turn
from app.services.ai.perspectivas import roles as roles_mod


def build_perspectiva_prompt(role: str, empresa_ctx: str) -> str:
    label = roles_mod.ROLE_LABEL.get(role, role)
    banco = "\n".join(f"    · {t}" for t in roles_mod.ROLE_BANK.get(role, []))
    return (
        f"Eres Todd, el secretario del consejo de Gobernia. Estás entrevistando a un {label} de la "
        f"empresa «{empresa_ctx or 'la empresa'}» para conocer SU perspectiva. Habla en español, "
        "cálido y breve. Haces UNA pregunta a la vez.\n\n"
        "IMPORTANTE: pregunta SOLO lo que este rol conoce de primera mano. NO le pidas datos internos "
        "que no le corresponden (finanzas internas, nómina, RH) si el rol es cliente o proveedor.\n\n"
        "TEMAS SUGERIDOS PARA ESTE ROL (guía; adapta según responda):\n" + banco + "\n\n"
        "REGLAS:\n"
        "1. Preguntas CONCRETAS y específicas, una a la vez. Nada de «cuéntame de la empresa».\n"
        "2. Ofrece 'single_choice' con 'options' cuando la respuesta sea acotada; si es abierta usa 'text'.\n"
        "3. Un «no sé / no aplica» es válido: regístralo y avanza; nunca te atores.\n"
        "4. Acumula en 'state' lo que aprendas (percepciones, fortalezas, quejas, sugerencias).\n"
        "5. La entrevista es CORTA (5–8 preguntas). Pon 'done': true con un cierre cálido de agradecimiento "
        "cuando tengas suficiente."
    )


def run_perspectiva_turn(messages: list[dict], state: dict | None,
                         role: str, empresa_ctx: str) -> dict:
    """Siguiente turno de la entrevista de perspectiva (Sonnet, tool use forzado).
    Sin API key → turno determinista mínimo (dev/tests sin red)."""
    if not settings.ANTHROPIC_API_KEY:
        return {"message": "Hola, soy Todd. (Modo sin IA) ¿Qué es lo que más valoras de la empresa?",
                "options": None, "input": "text", "state": state or {}, "done": False}
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=4096,
        system=build_perspectiva_prompt(role, empresa_ctx),
        messages=build_anthropic_messages(messages),
        tools=[RESPONSE_TOOL], tool_choice={"type": "tool", "name": "responder_turno"},
    )
    block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    parsed = dict(block.input) if block is not None and isinstance(block.input, dict) else {}
    return _normalize_turn(parsed)
