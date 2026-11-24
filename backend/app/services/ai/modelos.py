"""Cómo llamar a la IA según la generación del modelo.

Familia 4.x (Opus 4.8, Sonnet 4.6, Haiku 4.5): se puede OBLIGAR a la IA a contestar con una
herramienta (tool_choice forzado) y, si no se le pide, no piensa antes de responder. Con ellos
todo se manda EXACTAMENTE como siempre.

Modelos nuevos (Opus 5.5, Sonnet 5.5 y los que sigan): el tool_choice forzado da error 400 y la
IA piensa antes de responder (lo que piensa cuenta dentro de max_tokens; `effort` controla cuánto
piensa). Con ellos la herramienta se pide en la instrucción, se deja espacio para pensar, se usa
streaming (la respuesta puede tardar más de lo que aguanta una llamada normal) y se comprueba que
la haya usado; si no, se pide una vez más.

En Sonnet 5.5 se puede pedir que NO piense antes de contestar (thinking "between_tools"), como
hacía Sonnet 4.6: más rápido. Opus 5.5 siempre piensa. Las respuestas de los modelos nuevos pueden
empezar con bloques de pensamiento: el texto se lee con `texto()`, nunca con content[0].text.

Así, cambiar de modelo (o regresar al anterior) es solo cambiar DIAGNOSTICO_AI_MODEL / AI_MODEL.
"""
import logging

from app.core.config import settings

_log = logging.getLogger(__name__)


def _stream_with_retry(client, **kwargs):
    # Se importa al llamar: agents/base.py también usa este módulo.
    from app.services.ai.agents import base
    return base._stream_with_retry(client, **kwargs)


def ajustes_ai(en_vivo: bool = False) -> dict:
    """Esfuerzo y pensamiento configurados para las llamadas con AI_MODEL. `en_vivo`: alguien está
    esperando la respuesta en pantalla (entrevista y chats de Todd, chat del Consejo…)."""
    return {"effort": settings.AI_EFFORT_EN_VIVO if en_vivo else settings.AI_EFFORT,
            "thinking": settings.AI_THINKING}


_FAMILIA_ANTERIOR = ("claude-opus-4", "claude-sonnet-4", "claude-haiku-4")
_ADMITEN_NO_PENSAR = ("claude-sonnet-5-5",)  # thinking "between_tools"; cualquier otro modelo da 400
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


def opciones_del_modelo(model: str, effort: str | None = None, thinking: str | None = None) -> dict:
    """Esfuerzo y pensamiento, solo para los modelos nuevos (a los 4.x no se les cambia nada).
    `thinking="between_tools"`: que no piense antes de contestar. Solo Sonnet 5.5 lo acepta, y con
    esfuerzo high o menor; en los demás casos se deja el pensamiento adaptativo del modelo."""
    if not es_generacion_nueva(model):
        return {}
    opciones: dict = {}
    if effort:
        opciones["output_config"] = {"effort": effort}
    if (thinking == "between_tools" and (model or "").strip().startswith(_ADMITEN_NO_PENSAR)
            and effort not in ("xhigh", "max")):
        opciones["thinking"] = {"type": "between_tools"}
    return opciones


def texto(response) -> str:
    """El texto de la respuesta, sin los bloques de pensamiento ni de herramientas.
    (En los 4.x es lo mismo que content[0].text; en los nuevos el primer bloque puede ser pensamiento.)"""
    def es_texto(b) -> bool:
        tipo = getattr(b, "type", None)
        if isinstance(tipo, str):
            return tipo == "text"
        return isinstance(getattr(b, "text", None), str)  # bloque sin tipo (dobles de prueba)

    return "".join(b.text or "" for b in (getattr(response, "content", None) or []) if es_texto(b))


def pedir_texto(llamar, client, *, model: str, messages: list, max_tokens: int,
                effort: str | None = None, thinking: str | None = None, **kwargs):
    """Una llamada que contesta con texto libre. Devuelve el Message (léelo con `texto()`).
    En la familia 4.x: `llamar(client, ...)` exactamente como siempre. En los nuevos: streaming,
    espacio para pensar y las opciones de esfuerzo/pensamiento."""
    if not es_generacion_nueva(model):
        return llamar(client, model=model, max_tokens=max_tokens, messages=messages, **kwargs)
    return _stream_with_retry(
        client, model=model, max_tokens=con_espacio_para_pensar(model, max_tokens), messages=messages,
        **opciones_del_modelo(model, effort, thinking), **kwargs,
    )


def _con_nota(system, nota: str):
    """Agrega la nota AL FINAL de las instrucciones (sin tocar la parte guardada en caché)."""
    if isinstance(system, list):
        return [*system, {"type": "text", "text": nota}]
    return f"{system}\n\n{nota}" if system else nota


_MARCAS_INTERNAS = ("<parameter", "</parameter", "<invoke", "</invoke")


def _texto_interno(valor) -> bool:
    """¿Se coló el formato interno de la IA dentro de un campo? (visto con Sonnet 5.5 en esfuerzo alto)"""
    if isinstance(valor, str):
        return any(m in valor for m in _MARCAS_INTERNAS)
    if isinstance(valor, dict):
        return any(_texto_interno(v) for v in valor.values())
    if isinstance(valor, list):
        return any(_texto_interno(v) for v in valor)
    return False


def _entrada_valida(entrada, esquema: dict) -> bool:
    """Revisión ligera: un dict, las listas como listas, los objetos como objetos y sin formato interno."""
    if not isinstance(entrada, dict) or _texto_interno(entrada):
        return False
    tipos = {"array": list, "object": dict}
    for campo, definicion in (esquema.get("properties") or {}).items():
        tipo = (definicion or {}).get("type")
        tipo = tipos.get(tipo) if isinstance(tipo, str) else None
        if tipo and campo in entrada and not isinstance(entrada[campo], tipo):
            return False
    return True


def _uso_la_herramienta(response, tool: dict) -> bool:
    """Usó la herramienta y su primera llamada (la que leen quienes piden) llegó bien formada."""
    for b in getattr(response, "content", None) or []:
        if getattr(b, "type", None) == "tool_use" and getattr(b, "name", None) == tool["name"]:
            return _entrada_valida(getattr(b, "input", None), tool.get("input_schema") or {})
    return False


def pedir_herramienta(llamar, client, *, model: str, tool: dict, system, messages: list,
                      max_tokens: int, effort: str | None = None, thinking: str | None = None,
                      transmitir=None, **kwargs):
    """Una llamada en la que la IA debe contestar con `tool`. Devuelve el Message.

    `llamar`: la función que hace la llamada en la familia 4.x (el _create_with_retry del módulo
    que pide, para que las pruebas que lo sustituyen sigan funcionando).
    `transmitir`: en los modelos nuevos, la función de streaming a usar (por defecto
    _stream_with_retry; Todd usa la suya para mostrar la pregunta mientras se escribe).
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
            nota += (" En tu respuesta anterior no la usaste o llegó mal formada: llámala una sola vez,"
                     " con cada campo en el formato que pide.")
        response = (transmitir or _stream_with_retry)(
            client, model=model, max_tokens=con_espacio_para_pensar(model, max_tokens),
            system=_con_nota(system, nota), messages=messages, tools=[tool],
            **opciones_del_modelo(model, effort, thinking), **kwargs,
        )
        if _uso_la_herramienta(response, tool):
            return response
        motivo = getattr(response, "stop_reason", None)
        _log.warning("%s no usó bien la herramienta %s (stop_reason=%s, intento %d)",
                     model, nombre, motivo, intento + 1)
        if motivo in ("refusal", "max_tokens", "model_context_window_exceeded"):
            break  # pedirlo igual otra vez daría lo mismo
    return response
