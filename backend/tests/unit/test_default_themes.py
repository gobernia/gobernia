from app.services.governance.default_themes import DEFAULT_THEMES


def test_catalog_has_13_themes():
    assert len(DEFAULT_THEMES) == 13


def test_catalog_type_counts():
    perm = [t for t in DEFAULT_THEMES if t["type"] == "permanente"]
    cob = [t for t in DEFAULT_THEMES if t["type"] == "cobertura"]
    assert len(perm) == 5
    assert len(cob) == 8
    assert all(t["every_n_sessions"] == 1 for t in perm)


def test_catalog_keys_unique():
    keys = [t["key"] for t in DEFAULT_THEMES]
    assert len(keys) == len(set(keys))


def test_cobertura_frequencies():
    by_key = {t["key"]: t["every_n_sessions"] for t in DEFAULT_THEMES}
    assert by_key["talento_sucesion"] == 2
    assert by_key["auditoria"] == 3
    assert by_key["planeacion_estrategica"] == 6
    assert by_key["evaluacion_consejo"] == 12
