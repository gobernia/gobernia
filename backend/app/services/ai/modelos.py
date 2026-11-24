"""Cómo llamar a la IA según la generación del modelo.

Familia 4.x (Opus 4.8, Sonnet 4.6, Haiku 4.5): se puede OBLIGAR a la IA a contestar con una
herramienta (tool_choice forzado) y, si no se le pide, no piensa antes de responder. Con ellos
todo se manda EXACTAMENTE como siempre.

Modelos nuevos (Opus 5.5, Sonnet 5.5 y los que sigan): el tool_choice forzado da error 400 y la
IA piensa antes de responder (lo que piensa cuenta dentro de max_tokens; `effort` controla cuánto
piensa). Con ellos la herramienta se pide en la instrucción, se deja espacio para pensar, se usa
streaming (la respuesta puede tardar más de lo que aguanta una llamada normal) y se comprueba que
la haya usado; si no, se pide una vez más.

Así, cambiar de modelo (o regresar al anterior) es solo cambiar DIAGNOSTICO_AI_MODEL / AI_MODEL.
"""
import logging

from app.services.ai.agents import base

_log = logging.getLogger(__name__)

_FAMILIA_ANTERIOR = ("claude-opus-4", "claude-sonnet-4", "claude-haiku-4")
MARGEN_PENSAMIENTO = 16000  # tokens extra para lo que la IA piensa antes de contestar
MAX_TOKENS_TOPE = 64000
_INTENTOS = 2


def es_generacion_nueva(model: str) -> bool:
    """True para los modelos que piensan siempre y no aceptan tool_choice forzado."""
    return not (model or "").strip().startswith(_FAMILIA_ANTERIOR)


def con_espacio_para_pensar(model: str, max_tokens: int) -> int:
    """max_tokens para la respuesta MÁS lo que la IA piense (solo en los modelos nuevos)."""
    if not es_generacion_nueva(model):
        return max_tokens
    return min(max_tokens + MARGEN_PENSAMIENTO, MAX_TOKENS_TOPE)


def opciones_de_esfuerzo(model: str, effort: str | None) -> dict:
    """El parámetro de esfuerzo solo para los modelos nuevos (a los 4.x no se les cambia nada)."""
    if effort and es_generacion_nueva(model):
        return {"output_config": {"effort": effort}}
    return {}


def _con_nota(system, nota: str):
    """Agrega la nota AL FINAL de las instrucciones (sin tocar la parte guardada en caché)."""
    if isinstance(system, list):
        return [*system, {"type": "text", "text": nota}]
    return f"{system}\n\n{nota}" if system else nota


def _uso_la_herramienta(response, nombre: str) -> bool:
    return any(getattr(b, "type", None) == "tool_use" and getattr(b, "name", None) == nombre
               for b in (getattr(response, "content", None) or []))


def pedir_herramienta(llamar, client, *, model: str, tool: dict, system, messages: list,
                      max_tokens: int, effort: str | None = None, **kwargs):
    """Una llamada en la que la IA debe contestar con `tool`. Devuelve el Message.

    `llamar`: la función que hace la llamada en la familia 4.x (el _create_with_retry del módulo
    que pide, para que las pruebas que lo sustituyen sigan funcionando).
    Si en los modelos nuevos la IA no usa la herramienta (o la rechaza: stop_reason "refusal"),
    se devuelve la última respuesta y quien llama aplica su respaldo, igual que hoy.
    """
    if not es_generacion_nueva(model):
        return llamar(client, model=model, max_tokens=max_tokens, system=system, messages=messages,
                      tools=[tool], tool_choice={"type": "tool", "name": tool["name"]}, **kwargs)

    nombre = tool["name"]
    response = None
    for intento in range(_INTENTOS):
        nota = (f"Entrega tu respuesta llamando a la herramienta '{nombre}'. "
                "Todo lo que entregues debe ir dentro de ella.")
        if intento:
            nota += " En tu respuesta anterior no la usaste: úsala ahora."
        response = base._stream_with_retry(
            client, model=model, max_tokens=con_espacio_para_pensar(model, max_tokens),
            system=_con_nota(system, nota), messages=messages, tools=[tool],
            **opciones_de_esfuerzo(model, effort), **kwargs,
        )
        if _uso_la_herramienta(response, nombre):
            return response
        motivo = getattr(response, "stop_reason", None)
        _log.warning("%s no usó la herramienta %s (stop_reason=%s, intento %d)",
                     model, nombre, motivo, intento + 1)
        if motivo in ("refusal", "max_tokens", "model_context_window_exceeded"):
            break  # pedirlo igual otra vez daría lo mismo
    return response
