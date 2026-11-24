"""Las etiquetas de cita de la búsqueda web no deben verse en el diagnóstico (pantalla, PDF) ni
pasarse a otra IA. Ejemplo tomado de un diagnóstico real."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.ai.citas import sin_citas
from app.services.ai.diagnostico_estrategico import parse_diagnostico

REAL = ('Madix, el competidor que usted identifica, es real y relevante, pero conviene dimensionarlo: '
        '<cite index="1-3">Madix tiene su sede en Terrell, Texas</cite>, <cite index="7-5">con más de 2.4 '
        'millones de pies cuadrados</cite>. La competencia lo hace al revés: <cite index="3-1,3-2,3-3">Madix '
        'se presenta como socio estratégico</cite>.\nOtro párrafo sin citas.')
LIMPIO = ('Madix, el competidor que usted identifica, es real y relevante, pero conviene dimensionarlo: '
          'Madix tiene su sede en Terrell, Texas, con más de 2.4 millones de pies cuadrados. La competencia '
          'lo hace al revés: Madix se presenta como socio estratégico.\nOtro párrafo sin citas.')


def test_sin_citas_quita_la_etiqueta_y_deja_el_texto():
    assert sin_citas(REAL) == LIMPIO
    assert sin_citas("Sin etiquetas: 3 < 5 y <b>no</b> se toca") == "Sin etiquetas: 3 < 5 y <b>no</b> se toca"
    assert sin_citas(None) == "" and sin_citas("") == ""


def test_el_diagnostico_nuevo_se_guarda_sin_etiquetas():
    import json
    raw = json.dumps({"sections": {"competencia": REAL}, "sources": []}, ensure_ascii=False)
    competencia = next(s for s in parse_diagnostico(raw)["sections"] if s["key"] == "competencia")
    assert competencia["body"] == LIMPIO


@pytest.mark.asyncio
async def test_los_diagnosticos_ya_guardados_se_muestran_sin_etiquetas():
    from app.core.dependencies import get_current_user_id, get_db
    from app.main import app
    diag = MagicMock(status="active", fail_reason=None, created_at=None)
    diag.content = {"sections": [{"key": "competencia", "title": "Competencia", "body": REAL}], "sources": []}
    res = MagicMock(); res.scalars.return_value.first.return_value = diag
    db = AsyncMock(); db.execute = AsyncMock(return_value=res)

    async def _db():
        yield db
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user_id] = lambda: "u1"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/diagnostico")
    finally:
        app.dependency_overrides.clear()
    assert r.json()["sections"][0]["body"] == LIMPIO
    assert "cite" in diag.content["sections"][0]["body"]  # lo guardado no se modifica


def test_el_pdf_sale_sin_etiquetas(monkeypatch):
    from app.services.pdf import diagnostico_pdf
    textos = []
    original = diagnostico_pdf.Paragraph
    monkeypatch.setattr(diagnostico_pdf, "Paragraph", lambda t, *a, **k: textos.append(t) or original(t, *a, **k))
    pdf = diagnostico_pdf.build_diagnostico_pdf(
        {"sections": [{"key": "competencia", "title": "Competencia", "body": REAL}]}, "Keting")
    assert pdf[:4] == b"%PDF"
    assert any("Terrell, Texas, con más" in t for t in textos)
    assert not any("cite" in t for t in textos)


def test_la_foda_recibe_el_texto_sin_etiquetas(monkeypatch):
    from app.services.ai import foda
    enviado = {}

    def fake_create(client, **kw):
        enviado["user"] = kw["messages"][0]["content"]
        raise RuntimeError("basta con ver lo que se mandó")
    monkeypatch.setattr(foda.settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(foda, "_create_with_retry", fake_create)
    try:
        foda.generate_foda({}, {"sections": [{"key": "competencia", "title": "Competencia", "body": REAL}]}, {}, [])
    except Exception:
        pass
    assert "Terrell, Texas, con más" in enviado.get("user", "") and "cite" not in enviado["user"]
