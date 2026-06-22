"""Fase externa de Todd: banco PESTEL (factores del entorno) + metas base + prompt externo.
'PESTEL' es término interno; Todd no lo menciona al usuario.
"""
import json

PESTEL_CATS = ["politicos", "economicos", "sociales", "tecnologicos", "ambiental", "legal"]

PESTEL_BANK = {
    "politicos": [
        "Cambios políticos (elecciones, reestructuras de gobierno)",
        "Cambios en poderes o estructura de sindicatos",
        "Afectación de relaciones exteriores por eventos en otros países",
        "Burocracia o corrupción en los procesos de gestión pública",
        "Apoyo al emprendimiento mediante programas sociales",
    ],
    "economicos": [
        "Nuevos impuestos o aranceles",
        "Recesión económica por factores globales o federales",
        "Devaluación del peso vs. dólar u otro tipo de cambio",
        "Transacciones con entidades de recursos de dudosa procedencia",
        "Cambios contables exigidos por dependencias de gobierno",
        "Disputas comerciales que afecten la oferta/demanda",
        "Líneas de crédito que promuevan el crecimiento",
        "Pocas o nulas barreras de entrada para nuevos competidores",
    ],
    "sociales": [
        "Cambios en los hábitos de consumo de la sociedad",
        "Nuevas formas de interacción y comunicación entre personas",
        "Requerimientos de estándares de fiabilidad de productos/servicios",
        "Restricciones en publicidad para difundir contenido",
        "Inseguridad en los traslados de mercancías",
        "Robo de talento capacitado por empresas competidoras",
        "Modas, percepción o tendencias que afecten el consumo",
    ],
    "tecnologicos": [
        "Innovación constante en máquinas o herramientas que optimizan procesos",
        "Desarrollo de nuevos materiales o insumos con mejores beneficios",
        "Actualización de software con más funcionalidades",
        "Obsolescencia de tecnología por avances rápidos",
        "Adquisición de productos/servicios de forma online",
        "Aumento de la delincuencia cibernética",
        "Cambios en los modelos de adquisición de tecnología (leasing) y proveeduría",
    ],
    "ambiental": [
        "Protestas de grupos ambientalistas",
        "Nuevas normas ambientales más estrictas (local o federal)",
        "Aumento de costos de recursos naturales por escasez",
        "Nuevas pandemias o enfermedades",
        "Desastres naturales relacionados con el cambio climático",
    ],
    "legal": [
        "Permisos para la operación de la empresa",
        "Combate a la informalidad de las empresas",
        "Plagio de marca, secretos industriales o invenciones",
        "Corrupción en el otorgamiento de permisos de operación",
        "Demandas por incumplimiento de contratos (servicios, proveedores, empleados)",
        "Cambios en leyes de protección al trabajador",
    ],
}

METAS_BASE = [
    "Conseguir más y mejores clientes",
    "Tener empleados más comprometidos con los objetivos de la empresa",
    "Lograr mayor control de calidad en los procesos",
    "Tener claridad de procesos, funciones, responsabilidades y objetivos",
    "Delegar la dirección, formar un consejo y diversificarse/retirarse",
    "Conocer qué tan bien va respecto al potencial de mercado",
    "Reducir costos y maximizar ganancias/flujos",
]

_CAT_LABEL = {
    "politicos": "Políticos", "economicos": "Económicos", "sociales": "Sociales",
    "tecnologicos": "Tecnológicos", "ambiental": "Ambiental", "legal": "Legal",
}


def build_externo_prompt(state: dict | None, diagnostico_ctx: str) -> str:
    banco = "\n".join(
        f"- {_CAT_LABEL[c]}:\n" + "\n".join(f"    · {item}" for item in PESTEL_BANK[c])
        for c in PESTEL_CATS
    )
    estado_txt = ""
    if state:
        estado_txt = ("\n\nESTADO ACUMULADO ACTUAL (constrúyelo encima, no lo pierdas):\n"
                      + json.dumps(state, ensure_ascii=False))
    return (
        "Eres Todd, el secretario del consejo de Gobernia. Ya entrevistaste a la empresa por dentro "
        "y tienes su diagnóstico. Ahora exploras el ENTORNO EXTERNO: una segunda ronda de preguntas, "
        "cálida y profesional, en español, UNA pregunta a la vez.\n\n"
        "DIAGNÓSTICO DE LA EMPRESA (úsalo para preguntar con foco):\n" + (diagnostico_ctx or "(no disponible)") + "\n\n"
        "Explora los factores del entorno por categoría (políticos, económicos, sociales, tecnológicos, "
        "ambientales, legales) usando el banco de abajo como GUÍA (no obligatorio preguntar todo; salta lo "
        "que no aplique, profundiza lo relevante según el diagnóstico). Clasifica cada factor relevante como "
        "OPORTUNIDAD (juega a favor) o AMENAZA (en contra) en 'state.factores_externos' = "
        "{categoria: [{\"tipo\":\"oportunidad\"|\"amenaza\",\"texto\":\"...\"}]}.\n\n"
        "BANCO DE FACTORES POR CATEGORÍA (guía):\n" + banco + "\n\n"
        "REGLAS:\n"
        "1. Preguntas concretas, una a la vez. Usa 'single_choice' con 'options' cuando aplique "
        "(p. ej. [\"Sí, nos afecta\",\"Más o menos\",\"No\"]); si no, 'text'.\n"
        "2. NO uses tecnicismos como «análisis del entorno» ni nombres de marcos teóricos; habla natural.\n"
        "3. Mantén y DEVUELVE el 'state' completo: marca cada categoría en 'areas_cubiertas' "
        "(usa exactamente: politicos, economicos, sociales, tecnologicos, ambiental, legal) cuando la "
        "exploraste, y acumula 'factores_externos'.\n"
        "4. NUNCA repitas una pregunta ya hecha.\n"
        "5. Pon 'done': true SOLO cuando cubriste las 6 categorías; en ese turno 'message' es un cierre "
        "cálido (avisa que ahora priorizarán sus metas)."
        + estado_txt
    )


import anthropic
from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry
from app.services.ai.todd.agent import (
    build_anthropic_messages, _normalize_turn, enforce_coverage_against, RESPONSE_TOOL,
)


def _externo_call(messages: list[dict], system: str) -> dict:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=4096,
        system=system, messages=build_anthropic_messages(messages),
        tools=[RESPONSE_TOOL], tool_choice={"type": "tool", "name": "responder_turno"},
    )
    block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    parsed = dict(block.input) if block is not None and isinstance(block.input, dict) else {}
    return enforce_coverage_against(_normalize_turn(parsed), PESTEL_CATS)


def run_externo_turn(messages: list[dict], state: dict | None, diagnostico_ctx: str) -> dict:
    if not settings.ANTHROPIC_API_KEY:
        return {"message": "(sin IA) ¿Qué factores del entorno te preocupan?", "options": None,
                "input": "text", "state": state or {}, "done": False, "reanudar_desde": "continuar"}
    return _externo_call(messages, build_externo_prompt(state, diagnostico_ctx))


def run_externo_edit(messages: list[dict], edited_question: str, new_answer: str,
                     state: dict | None, diagnostico_ctx: str) -> dict:
    if not settings.ANTHROPIC_API_KEY:
        return {"message": "Listo, corregido. Sigamos.", "options": None, "input": "text",
                "state": state or {}, "done": False, "reanudar_desde": "rehacer"}
    nota = (f"\n\nEDICIÓN: el usuario corrigió «{edited_question}» → «{new_answer}». Revisa si invalida "
            "respuestas posteriores: 'continuar' si no, 'rehacer' si sí (avisa breve y repregunta).")
    return _externo_call(messages, build_externo_prompt(state, diagnostico_ctx) + nota)


_METAS_TOOL = {
    "name": "proponer_metas",
    "description": "Propone la lista de metas a priorizar, personalizada para la empresa.",
    "input_schema": {
        "type": "object",
        "properties": {"metas": {"type": "array", "items": {"type": "string"}}},
        "required": ["metas"],
    },
}


def generar_metas(diagnostico_ctx: str, state_interno: dict, state_externo: dict) -> list[str]:
    """Todd personaliza la lista de metas (parte de METAS_BASE, ajusta según interno+externo)."""
    if not settings.ANTHROPIC_API_KEY:
        return list(METAS_BASE)
    system = (
        "Eres Todd. Con base en el diagnóstico, los hallazgos internos y los factores externos de la "
        "empresa, propone entre 5 y 8 METAS/retos a priorizar, redactadas en primera persona del dueño "
        "(«Quiero…»). Parte de esta lista base y AJÚSTALA al caso (reformula, prioriza distinto, añade o "
        "quita): " + json.dumps(METAS_BASE, ensure_ascii=False) + ".\n\n"
        "DIAGNÓSTICO:\n" + (diagnostico_ctx or "(n/d)") + "\n"
        "INTERNO:\n" + json.dumps(state_interno or {}, ensure_ascii=False)[:2000] + "\n"
        "EXTERNO:\n" + json.dumps(state_externo or {}, ensure_ascii=False)[:2000]
    )
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=1024, system=system,
        messages=[{"role": "user", "content": "Propón las metas a priorizar."}],
        tools=[_METAS_TOOL], tool_choice={"type": "tool", "name": "proponer_metas"},
    )
    block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    metas = (block.input.get("metas") if block and isinstance(block.input, dict) else None) or []
    metas = [str(m) for m in metas if str(m).strip()]
    return metas or list(METAS_BASE)
