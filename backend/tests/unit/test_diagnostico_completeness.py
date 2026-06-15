from app.services.data_completeness import missing_diagnostico_data

OK = {"company": {"name": "ACME", "website": "https://acme.com", "competitors": ["Globex"]}}


def test_completo():
    assert missing_diagnostico_data(OK) == []


def test_sin_nombre():
    out = missing_diagnostico_data({"company": {"website": "https://a.com", "competitors": ["X"]}})
    assert out == ["el perfil de tu empresa (etapa 1)"]


def test_sin_web():
    out = missing_diagnostico_data({"company": {"name": "ACME", "competitors": ["X"]}})
    assert out == ["la página web de tu empresa (etapa 1)"]


def test_sin_competidores():
    out = missing_diagnostico_data({"company": {"name": "ACME", "website": "https://a.com", "competitors": []}})
    assert out == ["al menos un competidor (etapa 1)"]


def test_buffer_none():
    assert len(missing_diagnostico_data(None)) == 3
