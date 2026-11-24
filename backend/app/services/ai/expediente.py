"""El EXPEDIENTE de la empresa, para que Todd sepa de dónde salió un dato.

Todd (secretario) solo ve un resumen del tablero y del roadmap. Cuando el dueño le pregunta
«¿de dónde sacaste este 14%?», la cifra puede venir de la entrevista, del diagnóstico, de una
sesión del Consejo o del plan, que Todd no tiene a la vista. Sin esto, Todd llegó a "confesar"
que la había inventado cuando no era cierto.

Lógica pura (sin red ni base de datos):
- hojas(valor)                 → los textos de un JSON, con la ruta legible de cada uno
- buscar(fuentes, consulta)    → dónde aparece una cifra o frase, del más antiguo al más reciente
La carga desde la base de datos vive en api/v1/todd_secretario/service.py (cargar_expediente).
"""
import math
import re
import unicodedata
from datetime import datetime
from typing import Iterator

MAX_RESULTADOS = 8
_CONTEXTO = 180  # caracteres alrededor de la coincidencia

# Claves que nombran a un objeto: se usan como "ruta" legible de lo que contiene.
_CLAVES_NOMBRE = ("title", "titulo", "nombre", "label", "name", "kpi")
_VACIAS = {"de", "del", "la", "las", "el", "los", "una", "uno", "unos", "unas", "que", "con", "por",
           "para", "como", "esta", "este", "esto", "eso", "esa", "sus", "son", "fue", "hay", "donde",
           "obtuviste", "sacaste", "salio", "informacion", "dato", "cifra"}


def _base(c: str) -> str:
    """Un carácter en minúscula y sin acento (siempre 1 carácter: las posiciones no cambian)."""
    c = c.lower()[:1] or c
    d = unicodedata.normalize("NFKD", c)[:1]
    return "-" if c in "−–—" else d


def _normalizar(texto: str) -> str:
    return "".join(_base(c) for c in texto)


def hojas(valor, ruta: tuple[str, ...] = ()) -> Iterator[tuple[str, str]]:
    """(ruta, texto) de cada texto o número dentro de un JSON. Si un objeto tiene nombre o
    título, ese nombre se usa en la ruta (más legible que índices)."""
    if isinstance(valor, dict):
        nombre = next((str(valor[k]) for k in _CLAVES_NOMBRE if isinstance(valor.get(k), str) and valor[k].strip()), None)
        base = ruta + ((nombre[:60],) if nombre else ())
        for k, v in valor.items():
            yield from hojas(v, base + (() if nombre else (str(k),)))
    elif isinstance(valor, list):
        for v in valor:
            yield from hojas(v, ruta)
    elif isinstance(valor, bool) or valor is None:
        return
    elif isinstance(valor, (int, float)):
        yield " › ".join(ruta), str(valor)
    else:
        texto = str(valor).strip()
        if texto:
            yield " › ".join(ruta), texto


def _numeros(consulta: str) -> list[str]:
    return [n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", consulta)]


def _patron_numero(n: str) -> re.Pattern:
    # 14 no debe coincidir con 140, 2014 ni 14.5; 4.7 coincide con 4,7.
    cuerpo = re.escape(n).replace(r"\.", "[.,]")
    return re.compile(rf"(?<![\d.,]){cuerpo}(?![\d]|[.,]\d)")


def _palabras(consulta: str) -> list[str]:
    return [p for p in re.findall(r"[a-zñ]{4,}", _normalizar(consulta)) if p not in _VACIAS]


def _fecha(f) -> str:
    return f.strftime("%d/%m/%Y") if isinstance(f, datetime) else ""


def buscar(fuentes: list[dict], consulta: str, max_resultados: int = MAX_RESULTADOS) -> str:
    """fuentes: [{donde, fecha, ruta, texto}]. Devuelve el resultado listo para Todd."""
    consulta = (consulta or "").strip()
    numeros = [_patron_numero(n) for n in _numeros(consulta)]
    palabras = _palabras(consulta)
    if not numeros and not palabras:
        return "Dame una cifra o unas palabras concretas para buscar en el expediente."
    minimo = 0 if numeros else max(1, math.ceil(len(palabras) * 0.6))

    hallazgos = []
    for f in fuentes:
        norm = _normalizar(f["texto"])
        pos_num = [m.start() for p in numeros if (m := p.search(norm))]
        if len(pos_num) < len(numeros):
            continue  # todas las cifras pedidas deben estar
        pos_pal = [i for p in palabras if (i := norm.find(p)) >= 0]
        if len(pos_pal) < minimo:
            continue
        inicio = min(pos_num or pos_pal)
        a, b = max(0, inicio - _CONTEXTO), min(len(f["texto"]), inicio + _CONTEXTO)
        fragmento = ("…" if a else "") + f["texto"][a:b].replace("\n", " ").strip() + ("…" if b < len(f["texto"]) else "")
        hallazgos.append((10 * len(pos_num) + len(pos_pal), f, fragmento))

    if not hallazgos:
        return (f"No encontré «{consulta}» en el expediente de la empresa (entrevista, datos de la empresa, "
                "diagnóstico, sesiones del Consejo, plan, meses, tareas y acuerdos).")

    total = len(hallazgos)
    mejores = sorted(hallazgos, key=lambda h: -h[0])[:max_resultados]
    mejores.sort(key=lambda h: (h[1].get("fecha") is None,
                                h[1]["fecha"].timestamp() if isinstance(h[1].get("fecha"), datetime) else 0))
    lineas = [f"«{consulta}» aparece en {total} lugar(es) del expediente. "
              f"{'Estos son los más relevantes' if total > len(mejores) else 'Son estos'}, del más antiguo al más reciente:"]
    for n, (_, f, fragmento) in enumerate(mejores, 1):
        donde = f["donde"] + (f" › {f['ruta']}" if f.get("ruta") else "")
        fecha = _fecha(f.get("fecha"))
        lineas.append(f"{n}. {donde}" + (f" ({fecha})" if fecha else "") + f": «{fragmento}»")
    return "\n".join(lineas)
