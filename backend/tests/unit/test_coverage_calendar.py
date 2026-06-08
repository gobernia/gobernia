from app.models.board_theme import BoardTheme
from app.services.governance.default_themes import DEFAULT_THEMES
from app.services.governance.coverage_calendar import theme_sessions, scheduled_for_session


def _default_themes():
    return [
        BoardTheme(key=t["key"], label=t["label"], type=t["type"],
                   every_n_sessions=t["every_n_sessions"], active=True, order_index=i)
        for i, t in enumerate(DEFAULT_THEMES)
    ]


def _by_key():
    return {t.key: sessions for t, sessions in theme_sessions(_default_themes())}


def test_permanentes_en_todas_las_sesiones():
    by_key = _by_key()
    assert by_key["resultados_financieros"] == list(range(1, 13))
    assert by_key["riesgos_criticos"] == list(range(1, 13))


def test_bimestrales_escalonados():
    by_key = _by_key()
    assert by_key["talento_sucesion"] == [1, 3, 5, 7, 9, 11]
    assert by_key["tecnologia_ciberseguridad"] == [2, 4, 6, 8, 10, 12]


def test_trimestrales_tres_vias():
    by_key = _by_key()
    assert by_key["auditoria"] == [1, 4, 7, 10]
    assert by_key["cumplimiento_normativo"] == [2, 5, 8, 11]
    assert by_key["esg"] == [3, 6, 9, 12]


def test_semestral_y_anuales():
    by_key = _by_key()
    assert by_key["planeacion_estrategica"] == [1, 7]
    assert by_key["evaluacion_dg"] == [12]
    assert by_key["evaluacion_consejo"] == [11]


def test_inactivos_excluidos():
    themes = _default_themes()
    themes[5].active = False  # talento_sucesion (order_index 5)
    keys = {t.key for t, _ in theme_sessions(themes)}
    assert "talento_sucesion" not in keys


def test_scheduled_for_session_mes_1():
    sched = scheduled_for_session(_default_themes(), 1)
    perm = {t.key for t in sched["permanente"]}
    cob = {t.key for t in sched["cobertura"]}
    assert perm == {"seguimiento_acuerdos", "resultados_financieros",
                    "resultados_operativos", "kpis_estrategicos", "riesgos_criticos"}
    assert "auditoria" in cob and "talento_sucesion" in cob and "planeacion_estrategica" in cob
    assert "cumplimiento_normativo" not in cob and "esg" not in cob and "tecnologia_ciberseguridad" not in cob
