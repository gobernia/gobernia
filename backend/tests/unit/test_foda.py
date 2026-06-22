from app.services.ai.foda import _foda_fallback, generate_foda


HALLAZGOS = {
    "financiero": [{"tipo": "debilidad", "texto": "Márgenes apretados"}],
    "comercial": [{"tipo": "fortaleza", "texto": "Buen portafolio"},
                  {"tipo": "parcial", "texto": "Marca poco reconocida"}],
}
FACTORES = {
    "economicos": [{"tipo": "amenaza", "texto": "Nuevos aranceles"}],
    "tecnologicos": [{"tipo": "oportunidad", "texto": "Ventas online en auge"}],
}
METAS = ["Quiero más clientes", "Quiero reducir costos"]


def test_fallback_clasifica_interno_y_externo():
    f = _foda_fallback(HALLAZGOS, FACTORES, METAS)
    assert "Buen portafolio" in f["fortalezas"]
    assert "Márgenes apretados" in f["debilidades"]
    assert "Marca poco reconocida" in f["debilidades"]
    assert "Ventas online en auge" in f["oportunidades"]
    assert "Nuevos aranceles" in f["amenazas"]
    assert f["metas_priorizadas"] == METAS
    assert "sintesis" in f


def test_generate_foda_sin_api_key_usa_fallback(monkeypatch):
    import app.services.ai.foda as foda
    monkeypatch.setattr(foda.settings, "ANTHROPIC_API_KEY", "")
    out = generate_foda({}, {"fortalezas_debilidades": HALLAZGOS}, FACTORES, METAS)
    assert "Buen portafolio" in out["fortalezas"]
    assert out["metas_priorizadas"] == METAS


def test_generate_foda_toma_hallazgos_del_diagnostico_o_memory(monkeypatch):
    import app.services.ai.foda as foda
    monkeypatch.setattr(foda.settings, "ANTHROPIC_API_KEY", "")
    out = generate_foda({"hallazgos": HALLAZGOS}, {}, FACTORES, METAS)
    assert "Márgenes apretados" in out["debilidades"]
