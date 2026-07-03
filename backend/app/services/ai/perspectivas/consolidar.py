"""Consolida las perspectivas de los invitados en coincidencias / contradicciones / puntos ciegos.
Opus tool-use, sin web. Respeta el anonimato por rol (empleado/cliente nunca por nombre)."""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry
from app.services.ai.perspectivas import roles as roles_mod

CONSOLIDAR_TOOL = {
    "name": "consolidar_perspectivas",
    "description": "Sintetiza las perspectivas de varios invitados sobre una empresa.",
    "input_schema": {
        "type": "object",
        "properties": {
            "coincidencias": {"type": "array", "items": {"type": "string"},
                              "description": "Puntos donde las voces (incl. el dueño) coinciden."},
            "contradicciones": {"type": "array", "items": {"type": "string"},
                                "description": "Dónde chocan las percepciones (p. ej. el dueño cree X pero los clientes perciben Y)."},
            "puntos_ciegos": {"type": "array", "items": {"type": "string"},
                              "description": "Cosas que el dueño no mencionó y que otros sí ven."},
            "por_rol": {"type": "object",
                        "description": "Resumen agregado por rol. Para empleado/cliente NUNCA uses nombres."},
        },
        "required": ["coincidencias", "contradicciones", "puntos_ciegos", "por_rol"],
    },
}

_SYSTEM = (
    "Eres Todd, secretario del consejo de Gobernia. Recibes lo que el DUEÑO reportó y las "
    "perspectivas de varias personas (por rol). Sintetiza en español: coincidencias, contradicciones "
    "(lo más valioso: dónde el dueño y los demás perciben distinto) y puntos ciegos del dueño. "
    "REGLA DE ANONIMATO: para roles 'empleado' y 'cliente' habla SIEMPRE en agregado ('los empleados…', "
    "'2 de 3 clientes…') y NUNCA uses nombres; para 'directivo', 'socio' y 'proveedor' puedes atribuir."
)


def _conteo(invites: list[dict]) -> dict:
    out: dict[str, int] = {}
    for inv in invites:
        out[inv.get("role", "?")] = out.get(inv.get("role", "?"), 0) + 1
    return out


def _fallback(invites: list[dict]) -> dict:
    por_rol: dict[str, list[str]] = {}
    for inv in invites:
        role = inv.get("role", "?")
        textos = [m.get("text", "") for m in (inv.get("messages") or []) if m.get("role") == "user"]
        por_rol.setdefault(role, []).extend([t for t in textos if t.strip()])
    return {
        "coincidencias": [], "contradicciones": [], "puntos_ciegos": [],
        "por_rol": {r: " · ".join(v)[:800] for r, v in por_rol.items()},
        "conteo": _conteo(invites),
    }


def _invites_prompt(invites: list[dict]) -> str:
    partes = []
    for inv in invites:
        role = inv.get("role", "?")
        anon = role in roles_mod.ANONYMOUS_ROLES
        etiqueta = roles_mod.ROLE_LABEL.get(role, role)
        quien = etiqueta if anon or not inv.get("name") else f"{etiqueta} ({inv['name']})"
        textos = [m.get("text", "") for m in (inv.get("messages") or []) if m.get("role") == "user"]
        partes.append(f"[{quien}] " + " | ".join(t for t in textos if t.strip()))
    return "\n".join(partes)


def consolidar_perspectivas(owner_memory_buffer: dict, invites: list[dict]) -> dict:
    if not invites:
        return {"coincidencias": [], "contradicciones": [], "puntos_ciegos": [],
                "por_rol": {}, "conteo": {}}
    if not settings.ANTHROPIC_API_KEY:
        return _fallback(invites)
    hallazgos = (owner_memory_buffer or {}).get("hallazgos") or {}
    user = (
        "LO QUE REPORTÓ EL DUEÑO (hallazgos internos):\n"
        + json.dumps(hallazgos, ensure_ascii=False)[:2000] + "\n\n"
        "PERSPECTIVAS DE LOS INVITADOS (por rol):\n" + _invites_prompt(invites) + "\n\n"
        "Sintetiza en el JSON indicado, respetando el anonimato por rol."
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=300.0)
        response = _create_with_retry(
            client, model=settings.DIAGNOSTICO_AI_MODEL, max_tokens=2048,
            system=_SYSTEM, messages=[{"role": "user", "content": user}],
            tools=[CONSOLIDAR_TOOL], tool_choice={"type": "tool", "name": "consolidar_perspectivas"},
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        data = dict(block.input) if block and isinstance(block.input, dict) else {}
        return {
            "coincidencias": [str(x) for x in (data.get("coincidencias") or [])],
            "contradicciones": [str(x) for x in (data.get("contradicciones") or [])],
            "puntos_ciegos": [str(x) for x in (data.get("puntos_ciegos") or [])],
            "por_rol": data.get("por_rol") or {},
            "conteo": _conteo(invites),
        }
    except Exception:
        return _fallback(invites)
