"""
Bloques multimodales para Claude: PDFs e imágenes en base64.

Claude lee PDFs e imágenes de forma nativa (no hace falta extraer texto).
Los formatos que no puede leer (.xlsx, .docx, ...) no se adjuntan: se convierten
en una NOTA para que el agente pida al dueño subirlos en PDF.

- classify_docs(docs)           → (legibles con kind/media_type, ilegibles)
- readable_docs(docs, ...)      → (seleccionados, nota)  — clasifica y aplica los topes
- build_doc_blocks(documents)   → lista de bloques {"type": "document"|"image"|"text"}
"""
from pathlib import Path

# Tope de documentos por llamada (es decir, POR AGENTE: se aplica después del ruteo).
MAX_DOCS = 8

# Tope de bytes CRUDOS por llamada. La API de Anthropic corta la request a 32 MB y los
# documentos viajan en base64 (~4/3 del tamaño original), así que 15 MB crudos ≈ 20 MB de
# payload: deja margen para el prompt y evita el 400 por request demasiado grande.
MAX_DOC_BYTES_PER_CALL = 15 * 1024 * 1024

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


def classify_docs(docs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Separa los documentos en (legibles, ilegibles). Los legibles se enriquecen con
    `kind` y `media_type`. No aplica ningún tope: eso va después del ruteo por agente.
    """
    readable: list[dict] = []
    unreadable: list[dict] = []
    for d in docs:
        kind_media = classify_document(d.get("filename"))
        if kind_media is None:
            unreadable.append(d)
            continue
        kind, media_type = kind_media
        readable.append({**d, "kind": kind, "media_type": media_type})
    return readable, unreadable


def select_for_agent(
    readable: list[dict],
    unreadable: list[dict] | None = None,
    max_docs: int = MAX_DOCS,
    max_bytes: int = MAX_DOC_BYTES_PER_CALL,
) -> tuple[list[dict], str]:
    """
    De los documentos YA legibles y YA filtrados por competencia del agente (ordenados
    del más reciente al más viejo), devuelve los que se le adjuntan y la nota que explica
    lo que quedó fuera. Topes: `max_docs` documentos y `max_bytes` de bytes crudos.
    """
    within_count = readable[:max_docs]
    truncated = len(readable) - len(within_count)

    selected: list[dict] = []
    skipped_by_size: list[str] = []
    total = 0
    for d in within_count:
        size = int(d.get("size_bytes") or 0)
        if total + size > max_bytes:
            # No cabe. Seguimos con los demás: uno más chico (y más viejo) todavía puede entrar.
            skipped_by_size.append(d.get("filename") or "archivo")
            continue
        selected.append(d)
        total += size

    notes: list[str] = []
    names = [d.get("filename") or "archivo" for d in (unreadable or [])]
    if names:
        notes.append(
            "Documentos en un formato que no pude leer (pídele al usuario subirlos en PDF): "
            + ", ".join(names[:10]) + "."
        )
    if truncated > 0:
        notes.append(f"Había más documentos; solo leí los {max_docs} más recientes.")
    if skipped_by_size:
        notes.append(
            "Por límite de tamaño de la consulta no pude adjuntar (se priorizaron los más "
            "recientes): " + ", ".join(skipped_by_size[:10]) + "."
        )
    return selected, " ".join(notes)


def readable_docs(
    docs: list[dict],
    max_docs: int = MAX_DOCS,
    max_bytes: int = MAX_DOC_BYTES_PER_CALL,
) -> tuple[list[dict], str]:
    """Clasifica y aplica los topes de una sola vez. `docs` ya viene ordenado por recencia."""
    readable, unreadable = classify_docs(docs)
    return select_for_agent(readable, unreadable, max_docs=max_docs, max_bytes=max_bytes)


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
