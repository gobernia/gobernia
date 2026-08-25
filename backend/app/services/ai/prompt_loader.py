"""Carga los prompts de la IA desde backend/prompts/*.md.

Los prompts viven en archivos editables (no en el código) porque el cliente
los revisa y los seguirá ajustando: aplicar una nueva revisión = reemplazar
el archivo correspondiente, sin cirugía de código.

Se cachean en memoria al primer uso (los archivos se despliegan junto con el
código; un cambio de prompt requiere redeploy o reinicio, igual que antes).
"""
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parents[3] / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    path = _DIR / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Prompt no encontrado: {path} — ¿faltó desplegar backend/prompts/?"
        ) from e
