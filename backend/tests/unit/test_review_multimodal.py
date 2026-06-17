from app.services.ai.month_review import _build_review_content


def test_content_sin_documentos_es_string():
    out = _build_review_content("PROMPT", None)
    assert out == "PROMPT"
    assert _build_review_content("PROMPT", []) == "PROMPT"


def test_content_con_pdf_e_imagen_arma_bloques():
    docs = [
        {"kind": "pdf", "media_type": "application/pdf", "data": "QkFTRTY0", "label": "Doc A"},
        {"kind": "image", "media_type": "image/png", "data": "SU1H", "label": "Doc B"},
    ]
    out = _build_review_content("PROMPT", docs)
    assert isinstance(out, list)
    assert len(out) == 5
    assert out[0] == {"type": "text", "text": "Doc A"}
    assert out[1] == {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "QkFTRTY0"}}
    assert out[2] == {"type": "text", "text": "Doc B"}
    assert out[3] == {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "SU1H"}}
    assert out[4] == {"type": "text", "text": "PROMPT"}
