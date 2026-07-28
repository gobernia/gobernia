from app.services.governance.pilar_link import _norm, infer_pilar_index


# --- Fixtures de pilares reutilizables ---
def _pilares():
    return [
        {
            "nombre": "Crecimiento comercial",
            "objetivo": "Aumentar ventas online",
            "estrategias": ["Abrir canal digital", "Campañas de marketing"],
            "kpis": [{"label": "Ventas mensuales", "actual": 0, "meta": 100}],
        },
        {
            "nombre": "Eficiencia operativa",
            "objetivo": "Reducir costos de producción",
            "estrategias": ["Automatizar procesos", "Renegociar proveedores"],
            "kpis": [{"label": "Margen bruto", "actual": 0, "meta": 40}],
        },
    ]


# --- _norm ---
def test_norm_quita_acentos_puntuacion_y_colapsa():
    assert _norm("  Márgen, Brúto!!  ") == "margen bruto"
    assert _norm(None) == ""
    assert _norm("") == ""


# --- Voto por KPI ---
def test_match_por_kpi_exacto():
    assert infer_pilar_index(["Ventas mensuales"], None, _pilares()) == 0
    assert infer_pilar_index(["Margen bruto"], None, _pilares()) == 1


def test_match_por_kpi_con_acentos_y_mayusculas():
    assert infer_pilar_index(["VENTÁS Mensuáles"], None, _pilares()) == 0


def test_match_por_kpi_contencion_len_mayor_igual_4():
    # "ventas" contiene y es contenido por "ventas mensuales" (len>=4).
    assert infer_pilar_index(["Ventas"], None, _pilares()) == 0


def test_empate_por_kpi_gana_indice_mas_bajo():
    pilares = [
        {"kpis": [{"label": "Ventas"}]},
        {"kpis": [{"label": "Ventas"}]},
    ]
    assert infer_pilar_index(["Ventas"], None, pilares) == 0


def test_mas_votos_gana_sobre_indice_mas_bajo():
    pilares = [
        {"kpis": [{"label": "Ventas"}]},
        {"kpis": [{"label": "Costos"}, {"label": "Margen"}]},
    ]
    # Dos kpi_refs empatan con el pilar 1 → 2 votos vs 1 voto del pilar 0.
    assert infer_pilar_index(["Costos", "Margen"], None, pilares) == 1


# --- Fallback por texto ---
def test_sin_kpi_refs_fallback_por_texto():
    texto = "Automatizar procesos para reducir costos de produccion"
    assert infer_pilar_index(None, texto, _pilares()) == 1


def test_kpi_refs_sin_match_cae_a_fallback_por_texto():
    texto = "Aumentar ventas online con campanas de marketing"
    # kpi_ref que no empata con nada → usa texto → pilar 0.
    assert infer_pilar_index(["KPI Inexistente"], texto, _pilares()) == 0


def test_texto_sin_solape_suficiente_devuelve_none():
    # Solo una palabra en comun ("online") con el pilar 0 → score 1 < 2.
    texto = "Comprar equipo nuevo online"
    assert infer_pilar_index(None, texto, _pilares()) is None


# --- Bordes ---
def test_pilares_vacio_devuelve_none():
    assert infer_pilar_index(["Ventas"], "algo", []) is None
    assert infer_pilar_index(["Ventas"], "algo", None) is None


def test_kpi_refs_none_sin_texto_devuelve_none():
    assert infer_pilar_index(None, None, _pilares()) is None


def test_kpi_refs_vacio_sin_texto_devuelve_none():
    assert infer_pilar_index([], "", _pilares()) is None


def test_pilar_sin_kpis_no_revienta():
    pilares = [{"nombre": "Sin kpis", "objetivo": "algo"}]
    assert infer_pilar_index(["Ventas"], None, pilares) is None
