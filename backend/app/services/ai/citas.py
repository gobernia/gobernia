"""Con búsqueda web, la IA marca la fuente de cada frase con <cite index="1-3">…</cite>. Esas
etiquetas no deben verse en pantalla, en el PDF ni en el texto que se pasa a otra IA: se quita
la etiqueta y se deja el texto tal cual."""
import re

_CITA = re.compile(r"</?cite\b[^>]*>", re.IGNORECASE)


def sin_citas(texto: str | None) -> str:
    return _CITA.sub("", texto or "")
