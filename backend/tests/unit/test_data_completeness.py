from app.services.data_completeness import missing_company_data

OK = {
    "company": {"name": "ACME"},
    "kpis": {"finance": [{"label": "Margen", "current_value": 12.0, "unknown": False}]},
}


def test_completo():
    assert missing_company_data(OK) == []


def test_sin_nombre_de_empresa():
    out = missing_company_data({**OK, "company": {"industry": "retail"}})
    assert out == ["el perfil de tu empresa (etapa 1)"]


def test_sin_kpis_configurados():
    out = missing_company_data({**OK, "kpis": {}})
    assert out == ["tus KPIs (etapa 5)"]


def test_kpis_marcados_no_se():
    mb = {**OK, "kpis": {"finance": [
        {"label": "Margen", "current_value": None, "unknown": True},
        {"label": "Liquidez", "current_value": 1.2, "unknown": False},
    ]}}
    assert missing_company_data(mb) == ["1 de 2 KPIs sin valor (etapa 5)"]


def test_kpi_sin_current_value_cuenta_como_faltante():
    mb = {**OK, "kpis": {"finance": [{"label": "Margen", "unknown": False}]}}
    assert missing_company_data(mb) == ["1 de 1 KPIs sin valor (etapa 5)"]


def test_buffer_none():
    out = missing_company_data(None)
    assert len(out) == 2  # perfil + kpis
