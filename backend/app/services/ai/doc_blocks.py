"""
Bloques multimodales para Claude: PDFs e imágenes en base64.

Claude lee PDFs e imágenes de forma nativa (no hace falta extraer texto).
Los formatos que no puede leer (.xlsx, .docx, ...) no se adjuntan: se convierten
en una NOTA para que el agente pida al dueño subirlos en PDF.

- readable_docs(docs, max_docs) → (seleccionados, nota)
- build_doc_blocks(documents)   → lista de bloques {"type": "document"|"image"|"text"}
"""
from pathlib import Path

MAX_DOCS = 8

# extensión → (kind, media_type)
_READABLE_EXTENSIONS = {
    ".pdf":  ("pdf", "application/pdf"),
    ".png":  ("image", "image/png"),
    ".jpg":  ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
}


def classify_document(filename: str | None) -> tuple[str, str] | None:
    """(kind, media_type) si Claude puede leer el archivo; None si no."""
    ext = Path(filename or "").suffix.lower()
    return _READABLE_EXTENSIONS.get(ext)


def readable_docs(docs: list[dict], max_docs: int = MAX_DOCS) -> tuple[list[dict], str]:
    """
    De una lista de documentos (dicts con al menos `filename`, ya ordenados por
    prioridad/recencia), devuelve los legibles por Claude — hasta `max_docs` —
    enriquecidos con `kind` y `media_type`, y una nota sobre los que quedaron fuera.
    """
    readable: list[dict] = []
    unreadable: list[str] = []
    for d in docs:
        kind_media = classify_document(d.get("filename"))
        if kind_media is None:
            unreadable.append(d.get("filename") or "archivo")
            continue
        kind, media_type = kind_media
        readable.append({**d, "kind": kind, "media_type": media_type})

    selected = readable[:max_docs]
    truncated = len(readable) - len(selected)

    notes: list[str] = []
    if unreadable:
        notes.append(
            "Documentos en un formato que no pude leer (pídele al usuario subirlos en PDF): "
            + ", ".join(unreadable[:10]) + "."
        )
    if truncated > 0:
        notes.append(f"Había más documentos; solo leí los {max_docs} más recientes.")
    return selected, " ".join(notes)


def build_doc_blocks(documents: list[dict] | None) -> list[dict]:
    """
    documents: [{kind, media_type, data (base64 str), label}]
    → [{"type":"text", "text": label}, {"type":"document"|"image", "source": {...}}, ...]
    """
    blocks: list[dict] = []
    for d in (documents or []):
        if d.get("label"):
            blocks.append({"type": "text", "text": d["label"]})
        block_type = "document" if d.get("kind") == "pdf" else "image"
        blocks.append({
            "type": block_type,
            "source": {
                "type": "base64",
                "media_type": d["media_type"],
                "data": d["data"],
            },
        })
    return blocks
