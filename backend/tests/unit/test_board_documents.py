"""
El consejo lee el board pack: bloques multimodales, ruteo por rol, tool-use y
normalización retrocompatible de findings/alerts.
"""
from types import SimpleNamespace
from unittest.mock import patch

from app.schemas.board_session import normalize_agent_analyses, normalize_analysis
from app.schemas.etapa7 import DOCUMENT_TYPE_LABELS
from app.services.ai.agents.base import (
    AGENT_DOC_TYPES,
    ANALYSIS_TOOL,
    ANTI_HALLUCINATION_RULE,
    _placeholder_analysis,
    run_agent_analysis,
    run_agent_revision,
)
from app.services.ai.doc_blocks import (
    MAX_DOC_BYTES_PER_CALL,
    build_doc_blocks,
    readable_docs,
)


def _tool_response(payload: dict, name: str = "analisis_consejero"):
    """Respuesta de Claude con un bloque tool_use (tool-use forzado)."""
    block = SimpleNamespace(type="tool_use", name=name, input=payload)
    return SimpleNamespace(content=[block])


def _buf():
    return {
        "company": {"industry": "manufacturing"},
        "ai_context": {"company_narrative": "Empresa Demo SA de CV."},
        "agent_configs": {},
    }


def _pdf(name="estado.pdf", doc_type="financial"):
    return {"filename": name, "s3_key": f"k/{name}", "document_type": doc_type,
            "label": f"Documento «{name}»"}


# ── doc_blocks ────────────────────────────────────────────────────────────────

def test_readable_docs_filtra_xlsx_y_genera_nota():
    docs = [_pdf(), _pdf("hoja.xlsx", "financial"), _pdf("foto.png", "presentation")]
    selected, note = readable_docs(docs)
    assert [d["filename"] for d in selected] == ["estado.pdf", "foto.png"]
    assert selected[0]["kind"] == "pdf" and selected[0]["media_type"] == "application/pdf"
    assert selected[1]["kind"] == "image" and selected[1]["media_type"] == "image/png"
    assert "hoja.xlsx" in note and "PDF" in note


def test_readable_docs_topa_y_anota_truncado():
    docs = [_pdf(f"d{i}.pdf") for i in range(10)]
    selected, note = readable_docs(docs, max_docs=8)
    assert len(selected) == 8
    assert "8" in note


def test_readable_docs_sin_docs_no_hay_nota():
    assert readable_docs([]) == ([], "")


def test_build_doc_blocks_pdf_e_imagen():
    blocks = build_doc_blocks([
        {"kind": "pdf", "media_type": "application/pdf", "data": "QQ==", "label": "Doc A"},
        {"kind": "image", "media_type": "image/jpeg", "data": "Qg==", "label": "Doc B"},
    ])
    assert blocks[0] == {"type": "text", "text": "Doc A"}
    assert blocks[1]["type"] == "document"
    assert blocks[1]["source"] == {"type": "base64", "media_type": "application/pdf", "data": "QQ=="}
    assert blocks[3]["type"] == "image"


# ── Tipos de documento y ruteo por rol ────────────────────────────────────────

def test_nuevos_tipos_de_documento_tienen_label():
    assert DOCUMENT_TYPE_LABELS["presentation"] == "Presentación / material de la junta"
    assert DOCUMENT_TYPE_LABELS["audit_plan"] == "Plan de auditoría"
    assert "financial" in DOCUMENT_TYPE_LABELS and "other" in DOCUMENT_TYPE_LABELS


def test_ruteo_financial_al_cfo_no_al_cso():
    assert "financial" in AGENT_DOC_TYPES["CFO"]
    assert "financial" not in AGENT_DOC_TYPES["CSO"]


def test_ruteo_presentation_al_cso_no_al_cfo():
    assert "presentation" in AGENT_DOC_TYPES["CSO"]
    assert "presentation" not in AGENT_DOC_TYPES["CFO"]


def test_ruteo_auditor_y_cro():
    # `other` es material de apoyo general: lo leen todos (ver test más abajo).
    assert AGENT_DOC_TYPES["Auditor"] == {"audit_plan", "financial", "internal_rules",
                                          "bylaws", "other"}
    assert AGENT_DOC_TYPES["CRO"] == {"financial", "audit_plan", "presentation", "other"}


# ── run_agent_analysis: tool-use + documentos adjuntos ────────────────────────

_PAYLOAD = {
    "summary": "Margen bajo.",
    "findings": [{"texto": "Margen 5%", "fuente": "Estado de resultados, p. 4"}],
    "alerts": [{"nivel": "rojo", "texto": "Liquidez crítica", "fuente": "Balance, p. 2"}],
    "recommendations": ["Renegociar deuda en 30 días (CFO)."],
    "preguntas": ["¿Cuánta caja queda a 60 días?"],
}


def _run_with_capture(**kwargs):
    """Corre run_agent_analysis con Claude mockeado y devuelve (resultado, kwargs del create)."""
    captured = {}

    def fake_create(**create_kwargs):
        captured.update(create_kwargs)
        return _tool_response(_PAYLOAD)

    with patch("app.services.ai.agents.base.settings") as mock_settings, \
         patch("app.services.ai.agents.base.anthropic.Anthropic") as mock_client:
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.AI_MODEL = "claude-sonnet-4-6"
        mock_client.return_value.messages.create.side_effect = fake_create
        result = run_agent_analysis("CFO", _buf(), None, 2026, 6, **kwargs)
    return result, captured


def test_analysis_devuelve_shape_nuevo_con_tool_use():
    result, captured = _run_with_capture()
    # Mismo contenido que _PAYLOAD, pero sin documentos adjuntos no hay fuente que citar:
    # el backend las vacía (ver test_sin_documentos_las_fuentes_se_fuerzan_vacias).
    assert result["summary"] == _PAYLOAD["summary"]
    assert result["findings"][0]["texto"] == "Margen 5%"
    assert result["alerts"][0]["nivel"] == "rojo"
    assert result["recommendations"] == _PAYLOAD["recommendations"]
    assert result["preguntas"] == _PAYLOAD["preguntas"]
    # tool-use forzado
    assert captured["tools"] == [ANALYSIS_TOOL]
    assert captured["tool_choice"] == {"type": "tool", "name": "analisis_consejero"}
    # regla antialucinación en el system prompt
    assert "DEBES citar la fuente" in captured["system"]
    assert "NUNCA inventes" in ANTI_HALLUCINATION_RULE


def test_analysis_adjunta_los_documentos_como_bloques():
    docs = [{"kind": "pdf", "media_type": "application/pdf", "data": "QQ==",
             "label": "Documento «estado.pdf»"}]
    _, captured = _run_with_capture(documents=docs, documents_note="Hay un Excel que no pude leer.")
    content = captured["messages"][0]["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "Documento «estado.pdf»"}
    assert content[1]["type"] == "document"
    assert "Hay un Excel que no pude leer." in content[-1]["text"]


def test_analysis_sin_documentos_manda_texto_plano():
    _, captured = _run_with_capture()
    assert isinstance(captured["messages"][0]["content"], str)
    assert "No se adjuntó ningún documento" in captured["messages"][0]["content"]


def test_revision_devuelve_el_mismo_esquema_con_tool_use():
    captured = {}

    def fake_create(**create_kwargs):
        captured.update(create_kwargs)
        return _tool_response(_PAYLOAD)

    with patch("app.services.ai.agents.base.settings") as mock_settings, \
         patch("app.services.ai.agents.base.anthropic.Anthropic") as mock_client:
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.AI_MODEL = "claude-sonnet-4-6"
        mock_client.return_value.messages.create.side_effect = fake_create
        result = run_agent_revision(
            "CFO", {"summary": "viejo"}, {"missing_risks": ["riesgo X"]},
            _buf(), None, 2026, 6,
        )
    assert result["summary"] == _PAYLOAD["summary"]
    assert result["findings"][0]["texto"] == "Margen 5%"
    assert result["recommendations"] == _PAYLOAD["recommendations"]
    # El análisis inicial no citaba ninguna fuente → la revisión tampoco puede inventarlas
    # (ver test_revision_no_puede_inventar_fuentes_nuevas).
    assert result["findings"][0]["fuente"] == ""
    assert captured["tool_choice"] == {"type": "tool", "name": "analisis_consejero"}
    # la revisión NO recibe documentos
    assert isinstance(captured["messages"][0]["content"], str)


def test_placeholder_tiene_shape_nuevo():
    with patch("app.services.ai.agents.base.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = ""
        p = _placeholder_analysis("CFO", 2026, 6)
    assert p["findings"] == [{"texto": "Datos recibidos correctamente.", "fuente": ""}]
    assert p["alerts"] == [] and p["preguntas"] == []


# ── Retrocompatibilidad: sesiones viejas (findings/alerts como list[str]) ──────

def test_normalize_analysis_legacy_strings():
    legacy = {
        "summary": "S",
        "findings": ["a", "b"],
        "alerts": ["alerta vieja"],
        "recommendations": ["r1"],
    }
    out = normalize_analysis(legacy)
    assert out["findings"] == [{"texto": "a", "fuente": ""}, {"texto": "b", "fuente": ""}]
    assert out["alerts"] == [{"nivel": "ambar", "texto": "alerta vieja", "fuente": ""}]
    assert out["preguntas"] == []


def test_normalize_analysis_respeta_shape_nuevo_y_nivel_invalido():
    out = normalize_analysis({
        "summary": "S",
        "findings": [{"texto": "f", "fuente": "Doc, p. 1"}],
        "alerts": [{"nivel": "morado", "texto": "x", "fuente": ""}],
        "preguntas": ["¿y la caja?"],
    })
    assert out["findings"] == [{"texto": "f", "fuente": "Doc, p. 1"}]
    assert out["alerts"][0]["nivel"] == "ambar"   # nivel inválido → ambar
    assert out["preguntas"] == ["¿y la caja?"]


def test_normalize_agent_analyses_por_agente():
    out = normalize_agent_analyses({"CFO": {"summary": "S", "findings": ["a"]}})
    assert out["CFO"]["findings"] == [{"texto": "a", "fuente": ""}]


# ── P0-b · Presupuesto de bytes por llamada (límite de 32 MB de Anthropic) ─────

def test_presupuesto_de_bytes_es_constante_conservadora():
    # 15 MB crudos ≈ 20 MB en base64: bien por debajo de los 32 MB del request.
    assert MAX_DOC_BYTES_PER_CALL == 15 * 1024 * 1024


def test_readable_docs_corta_por_bytes_y_lo_dice_en_la_nota():
    """4 PDFs de 8 MB no caben en una sola llamada: se adjuntan los que quepan."""
    docs = [{**_pdf(f"d{i}.pdf"), "size_bytes": 8 * 1024 * 1024} for i in range(4)]
    selected, note = readable_docs(docs)
    assert [d["filename"] for d in selected] == ["d0.pdf"]   # el más reciente primero
    assert "tamaño" in note.lower()
    assert "d1.pdf" in note


def test_readable_docs_sin_size_bytes_no_corta():
    docs = [_pdf("a.pdf"), _pdf("b.pdf")]
    selected, note = readable_docs(docs)
    assert len(selected) == 2 and note == ""


def test_readable_docs_mete_los_que_quepan_priorizando_recientes():
    docs = [
        {**_pdf("reciente.pdf"), "size_bytes": 14 * 1024 * 1024},
        {**_pdf("viejo_grande.pdf"), "size_bytes": 9 * 1024 * 1024},
        {**_pdf("viejo_chico.pdf"), "size_bytes": 512 * 1024},
    ]
    selected, note = readable_docs(docs)
    assert [d["filename"] for d in selected] == ["reciente.pdf", "viejo_chico.pdf"]
    assert "viejo_grande.pdf" in note


# ── P2-a · El tipo `other` lo leen todos los consejeros ───────────────────────

def test_other_lo_leen_todos_los_agentes():
    for agent in ("CFO", "CSO", "CRO", "Auditor"):
        assert "other" in AGENT_DOC_TYPES[agent], agent


# ── P1-a · tool_use vacío o truncado NO produce tarjeta en blanco ─────────────

def _run_with_response(response, **kwargs):
    with patch("app.services.ai.agents.base.settings") as mock_settings, \
         patch("app.services.ai.agents.base.anthropic.Anthropic") as mock_client:
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.AI_MODEL = "claude-sonnet-4-6"
        mock_client.return_value.messages.create.return_value = response
        return run_agent_analysis("CFO", _buf(), None, 2026, 6, **kwargs)


def test_tool_input_vacio_cae_a_placeholder_no_a_tarjeta_en_blanco():
    result = _run_with_response(_tool_response({}))
    assert result["summary"], "no puede quedar una tarjeta sin resumen"
    assert "no logró" in result["summary"] or "No pude" in result["summary"]


def test_tool_input_sin_summary_cae_a_placeholder():
    result = _run_with_response(_tool_response({"findings": [], "alerts": []}))
    assert result["summary"]
    assert result["recommendations"]


def test_stop_reason_max_tokens_cae_a_placeholder():
    truncado = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="analisis_consejero", input=_PAYLOAD)],
        stop_reason="max_tokens",
    )
    result = _run_with_response(truncado)
    assert result != _PAYLOAD
    assert result["summary"]


def test_analisis_pide_4096_tokens():
    _, captured = _run_with_capture()
    assert captured["max_tokens"] == 4096


# ── P3 · La regla antialucinación se verifica en el backend ───────────────────

def test_sin_documentos_las_fuentes_se_fuerzan_vacias():
    """El modelo cita una fuente que nunca se le adjuntó → se limpia."""
    result = _run_with_response(_tool_response(_PAYLOAD))   # sin documents=
    assert result["findings"][0]["fuente"] == ""
    assert result["alerts"][0]["fuente"] == ""
    assert result["findings"][0]["texto"] == "Margen 5%"    # el texto se conserva


def test_con_documentos_las_fuentes_se_conservan():
    docs = [{"kind": "pdf", "media_type": "application/pdf", "data": "QQ==", "label": "Doc"}]
    result = _run_with_response(_tool_response(_PAYLOAD), documents=docs)
    assert result["findings"][0]["fuente"] == "Estado de resultados, p. 4"


def test_revision_no_puede_inventar_fuentes_nuevas():
    """La revisión no ve los documentos: solo puede reusar las fuentes del análisis inicial."""
    inicial = {
        "summary": "Inicial",
        "findings": [{"texto": "Margen 5%", "fuente": "Estado de resultados, p. 4"}],
        "alerts": [],
        "recommendations": [],
        "preguntas": [],
    }
    revisado = {
        "summary": "Revisado",
        "findings": [
            {"texto": "Margen 5%", "fuente": "Estado de resultados, p. 4"},   # válida
            {"texto": "Deuda alta", "fuente": "Balance general, p. 9"},        # inventada
        ],
        "alerts": [{"nivel": "rojo", "texto": "Liquidez", "fuente": "Flujo de caja, p. 1"}],
        "recommendations": ["Renegociar"],
        "preguntas": [],
    }
    with patch("app.services.ai.agents.base.settings") as mock_settings, \
         patch("app.services.ai.agents.base.anthropic.Anthropic") as mock_client:
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.AI_MODEL = "claude-sonnet-4-6"
        mock_client.return_value.messages.create.return_value = _tool_response(revisado)
        out = run_agent_revision(
            "CFO", inicial, {"missing_risks": ["riesgo X"]}, _buf(), None, 2026, 6,
        )

    assert out["summary"] == "Revisado"
    assert out["findings"][0]["fuente"] == "Estado de resultados, p. 4"   # se conserva
    assert out["findings"][1]["fuente"] == ""                             # inventada → vacía
    assert out["alerts"][0]["fuente"] == ""                               # inventada → vacía
    assert out["alerts"][0]["texto"] == "Liquidez"                        # el texto se conserva
