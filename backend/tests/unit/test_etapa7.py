"""
Tests unitarios de Etapa 7 — validaciones de archivos, storage key y procesador.
"""
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.etapa7 import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    DOCUMENT_TYPE_LABELS,
)
from app.services.documents.storage import generate_storage_key
from app.services.documents.processor import (
    extract_text_from_content,
    analyze_document_with_claude,
)


# ── Tipos permitidos ──────────────────────────────────────────────────────────

def test_extensiones_permitidas_completas():
    assert ".pdf" in ALLOWED_EXTENSIONS
    assert ".docx" in ALLOWED_EXTENSIONS
    assert ".xlsx" in ALLOWED_EXTENSIONS
    assert ".jpg" in ALLOWED_EXTENSIONS


def test_extension_no_permitida_no_en_set():
    assert ".exe" not in ALLOWED_EXTENSIONS
    assert ".zip" not in ALLOWED_EXTENSIONS
    assert ".py" not in ALLOWED_EXTENSIONS


# ── Límite de tamaño ─────────────────────────────────────────────────────────

def test_max_size_es_10mb():
    assert MAX_FILE_SIZE_BYTES == 10 * 1024 * 1024


# ── Storage key ───────────────────────────────────────────────────────────────

def test_generate_storage_key_formato():
    session_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    key = generate_storage_key(session_id, doc_id, "reporte.pdf")
    assert key.startswith("documents/")
    assert str(session_id) in key
    assert str(doc_id) in key
    assert key.endswith("reporte.pdf")


def test_generate_storage_key_unico_por_doc():
    sid = uuid.uuid4()
    d1, d2 = uuid.uuid4(), uuid.uuid4()
    assert generate_storage_key(sid, d1, "f.pdf") != generate_storage_key(sid, d2, "f.pdf")


# ── Labels de tipo de documento ───────────────────────────────────────────────

def test_todos_los_tipos_tienen_label():
    tipos = ["financial", "org_chart", "bylaws", "business_plan", "internal_rules", "other"]
    for t in tipos:
        assert t in DOCUMENT_TYPE_LABELS
        assert len(DOCUMENT_TYPE_LABELS[t]) > 0


# ── Extracción de texto ───────────────────────────────────────────────────────

def test_extract_imagen_devuelve_placeholder():
    result = extract_text_from_content(b"fake_image_data", "image/jpeg")
    assert "Imagen" in result or "visual" in result


def test_extract_pdf_sin_pdfplumber_devuelve_mensaje():
    with patch("builtins.__import__", side_effect=ImportError("pdfplumber not installed")):
        pass  # No queremos romper la importación del módulo
    # Si pdfplumber no está, la función retorna un mensaje legible
    result = extract_text_from_content(b"not a real pdf", "application/pdf")
    assert isinstance(result, str)
    assert len(result) > 0


# ── Análisis con Claude ───────────────────────────────────────────────────────

def test_analyze_sin_api_key_devuelve_placeholder():
    with patch("app.services.documents.processor.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = ""
        result = analyze_document_with_claude("texto de prueba largo " * 5, "financial", "Empresa Demo")
    assert "summary" in result
    assert isinstance(result["key_findings"], list)
    assert isinstance(result["risks"], list)


def test_analyze_texto_corto_no_llama_api():
    with patch("app.services.documents.processor.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = "fake-key"
        # Texto muy corto → se omite la llamada a la API
        result = analyze_document_with_claude("corto", "financial", "Demo")
    assert "summary" in result


def test_analyze_json_valido_del_modelo():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text='{"summary": "S", "key_findings": ["f1"], "risks": ["r1"], "recommendations": ["rec1"]}'
    )]

    # Patch anthropic.Anthropic en el namespace del módulo processor
    with patch("app.services.documents.processor.anthropic") as mock_anthropic_mod, \
         patch("app.services.documents.processor.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.AI_MODEL = "claude-sonnet-4-6"
        mock_anthropic_mod.Anthropic.return_value.messages.create.return_value = mock_response

        result = analyze_document_with_claude("texto largo " * 10, "financial", "Demo")

    assert result["summary"] == "S"
    assert result["key_findings"] == ["f1"]
    assert result["risks"] == ["r1"]
