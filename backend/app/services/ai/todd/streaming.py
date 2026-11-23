"""Turnos de Todd EN VIVO: la pregunta llega al navegador mientras la IA termina de escribir el
expediente ('state'). La IA escribe primero 'message' (unos 2 s) y después el expediente
completo (en una entrevista avanzada, 10+ s); con esto la persona lee la pregunta sin esperar.

El turno que se guarda es EXACTAMENTE el mismo que sin streaming: aquí solo se observa lo que va
llegando; el expediente y su formato no cambian.
"""
import json
import logging
import time
from typing import Callable

import anthropic

from app.services.ai.agents.base import _RETRY_DELAYS, _RETRYABLE

_log = logging.getLogger(__name__)
_DEC = json.JSONDecoder()
_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


def _inicio_de_valor(txt: str, clave: str) -> int | None:
    """Posición donde empieza el valor de `clave` en el JSON parcial (primera aparición)."""
    i = txt.find(f'"{clave}"')
    if i < 0:
        return None
    c = txt.find(":", i + len(clave) + 2)
    if c < 0 or txt[i + len(clave) + 2:c].strip():
        return None
    j = c + 1
    while j < len(txt) and txt[j] in " \t\r\n":
        j += 1
    return j if j < len(txt) else None


def texto_parcial(txt: str, clave: str = "message") -> str:
    """El texto de `clave` que ya llegó, decodificado, aunque la cadena JSON siga abierta.
    Se detiene antes de un escape a medias (p. ej. '\\u00' sin terminar)."""
    j = _inicio_de_valor(txt, clave)
    if j is None or txt[j] != '"':
        return ""
    k, out = j + 1, []
    while k < len(txt):
        ch = txt[k]
        if ch == '"':
            break
        if ch != "\\":
            out.append(ch)
            k += 1
            continue
        if k + 1 >= len(txt):
            break
        sig = txt[k + 1]
        if sig != "u":
            out.append(_ESCAPES.get(sig, sig))
            k += 2
            continue
        try:
            if k + 6 > len(txt):
                break
            cp = int(txt[k + 2:k + 6], 16)
            avance = 6
            if 0xD800 <= cp <= 0xDBFF:  # emoji y otros: par sustituto, espera la segunda mitad
                if k + 12 > len(txt):
                    break
                if txt[k + 6:k + 8] == "\\u":
                    cp = 0x10000 + ((cp - 0xD800) << 10) + (int(txt[k + 8:k + 12], 16) - 0xDC00)
                    avance = 12
            out.append(chr(cp))
            k += avance
        except ValueError:
            break
    return "".join(out)


def _valor_completo(txt: str, clave: str):
    """El valor de `clave` solo si ya llegó completo; si no, None."""
    j = _inicio_de_valor(txt, clave)
    if j is None:
        return None
    try:
        return _DEC.raw_decode(txt, j)[0]
    except ValueError:
        return None


def campos_visibles(txt: str) -> dict:
    """Lo que ya se puede mostrar del turno: la pregunta (aunque vaya a medias) y, cuando ya
    llegaron completos, las opciones y el tipo de respuesta."""
    campos: dict = {"message": texto_parcial(txt)}
    opciones = _valor_completo(txt, "options")
    if isinstance(opciones, list):
        campos["options"] = [str(o) for o in opciones] or None
    tipo = _valor_completo(txt, "input")
    if tipo in ("text", "single_choice"):
        campos["input"] = tipo
    return campos


def stream_turno(client: anthropic.Anthropic, al_avanzar: Callable[[dict], None], **kwargs):
    """Como _create_with_retry, pero con streaming: llama a `al_avanzar(campos)` cada vez que
    hay más pregunta visible. Devuelve el Message final (el mismo que daría sin streaming).
    Si hay un reintento, la pregunta vuelve a empezar: cada aviso trae el texto completo."""
    # Sin esto, la API junta la entrada de la herramienta y la entrega de golpe al final.
    kwargs["tools"] = [dict(t, eager_input_streaming=True) for t in kwargs["tools"]]
    last_exc: Exception | None = None
    for intento, espera in enumerate(_RETRY_DELAYS):
        if espera > 0:
            _log.warning("anthropic transient error (%s); retry en vivo %d/%d en %ds",
                         type(last_exc).__name__ if last_exc else "?", intento, len(_RETRY_DELAYS) - 1, espera)
            time.sleep(espera)
        try:
            parcial, ultimo, completo = "", None, False
            with client.messages.stream(**kwargs) as s:
                for ev in s:
                    if completo or ev.type != "content_block_delta":
                        continue
                    if getattr(ev.delta, "type", "") != "input_json_delta":
                        continue
                    parcial += ev.delta.partial_json
                    campos = campos_visibles(parcial)
                    if campos != ultimo:
                        ultimo = campos
                        al_avanzar(campos)
                        # Ya está todo lo visible: lo que sigue es el expediente.
                        completo = "input" in campos and _valor_completo(parcial, "message") is not None
                return s.get_final_message()
        except _RETRYABLE as e:
            last_exc = e
    assert last_exc is not None
    raise last_exc
