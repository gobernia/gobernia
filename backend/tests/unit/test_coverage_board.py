from types import SimpleNamespace

from app.models.board_theme import BoardTheme
from app.services.governance.coverage_board import coverage_status, coverage_rows


def test_status_en_tiempo():
    assert coverage_status("cobertura", 0) == "en_tiempo"
    assert coverage_status("cobertura", -1) == "en_tiempo"


def test_status_cobertura_escala():
    assert coverage_status("cobertura", 1) == "riesgo"
    assert coverage_status("cobertura", 2) == "atrasado"
    assert coverage_status("cobertura", 3) == "critico"


def test_status_permanente_escala_mas_rapido():
    assert coverage_status("permanente", 1) == "atrasado"
    assert coverage_status("permanente", 2) == "critico"


def _theme(key, type_, freq, order, active=True):
    return BoardTheme(key=key, label=key.title(), type=type_,
                      every_n_sessions=freq, active=active, order_index=order)


def test_coverage_rows():
    themes = [
        _theme("fin", "permanente", 1, 0),   # sesiones 1..12
        _theme("aud", "cobertura", 3, 1),    # sesiones 1,4,7,10
    ]
    months = [
        SimpleNamespace(covered_themes=["fin", "aud"]),  # mes 1
        SimpleNamespace(covered_themes=["fin"]),         # mes 2
    ]
    # mes activo = 5 → esperadas cuenta meses YA pasados (1..4, estrictamente < activo)
    rows = {r["key"]: r for r in coverage_rows(themes, months, active_index=5)}

    assert rows["fin"]["frecuencia_anual"] == 12
    assert rows["fin"]["esperadas"] == 4
    assert rows["fin"]["realizadas"] == 2
    assert rows["fin"]["estado"] == "critico"
    assert rows["aud"]["frecuencia_anual"] == 4
    assert rows["aud"]["esperadas"] == 2
    assert rows["aud"]["realizadas"] == 1
    assert rows["aud"]["estado"] == "riesgo"
