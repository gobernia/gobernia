from app.services.pdf.diagnostico_pdf import build_diagnostico_pdf, _split_fd


def test_split_fd_separa_fortalezas_y_debilidades():
    content = {"fortalezas_debilidades": {
        "comercial": [{"tipo": "fortaleza", "texto": "Propuesta clara"}],
        "financiero": [{"tipo": "debilidad", "texto": "Sin reserva"},
                       {"tipo": "parcial", "texto": "Costos parciales"}],
    }}
    fort, debil = _split_fd(content)
    assert [t for t, _a in fort] == ["Propuesta clara"]
    assert {t for t, _a in debil} == {"Sin reserva", "Costos parciales"}  # parcial cuenta como debilidad


def test_pdf_con_interno_y_riesgos_es_pdf_valido():
    content = {
        "fortalezas_debilidades": {"comercial": [{"tipo": "fortaleza", "texto": "Buena marca"}]},
        "riesgos": [{"riesgo": "Dependencia de pocos clientes", "severidad": "alta"}],
        "sections": [{"key": "competencia", "title": "Competencia", "body": "Texto."}],
        "sources": [{"title": "Sitio", "url": "https://x.com"}],
    }
    pdf = build_diagnostico_pdf(content, "Keting Media")
    assert pdf[:5] == b"%PDF-" and len(pdf) > 1000


def test_pdf_vacio_no_truena():
    assert build_diagnostico_pdf({}, None)[:5] == b"%PDF-"
