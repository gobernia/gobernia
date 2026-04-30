"""
Tests unitarios de Etapa 5 — motor de KPIs, filtros y alertas.
"""
import pytest

from app.schemas.etapa5 import KPIValueInput
from app.services.ai.kpi_engine import (
    build_kpi_templates,
    process_kpi_values,
    _run_alert_rules,
    _get_headcount_from_buffer,
    _KPI_MAP,
)


def _buf(industry="manufacturing", employees="11-50", revenue="1M-5M"):
    return {"company": {"industry": industry, "employees": employees, "annual_revenue": revenue}}


def _inputs(templates, overrides: dict | None = None):
    overrides = overrides or {}
    return [
        KPIValueInput(
            key=t.key,
            current_value=overrides.get(t.key, {}).get("current"),
            target_value=overrides.get(t.key, {}).get("target"),
            unknown=overrides.get(t.key, {}).get("unknown", False),
        )
        for t in templates
    ]


# ── Filtros de industria ──────────────────────────────────────────────────────

def test_manufactura_incluye_operacionales():
    templates = build_kpi_templates(_buf("manufacturing"))
    keys = {t.key for t in templates}
    # capacity_utilization y quality_returns visibles para no-servicios
    assert "capacity_utilization" in keys
    assert "quality_returns" in keys
    # otif solo para empresas avanzadas (200+ o 15M+)
    assert "otif" not in keys


def test_manufactura_avanzada_incluye_otif():
    templates = build_kpi_templates(_buf("manufacturing", "200+"))
    keys = {t.key for t in templates}
    assert "otif" in keys


def test_servicios_oculta_operacionales():
    for ind in ("professional_services", "health", "education", "technology", "other"):
        templates = build_kpi_templates(_buf(ind))
        keys = {t.key for t in templates}
        assert "capacity_utilization" not in keys, f"capacity_utilization visible en {ind}"
        assert "otif" not in keys, f"otif visible en {ind}"
        assert "quality_returns" not in keys, f"quality_returns visible en {ind}"


def test_empresa_pequena_oculta_avanzados():
    templates = build_kpi_templates(_buf("manufacturing", "1-10", "less_1M"))
    keys = {t.key for t in templates}
    assert "debt_capital" not in keys
    assert "accounts_receivable" not in keys


def test_empresa_grande_empleados_muestra_avanzados():
    templates = build_kpi_templates(_buf("manufacturing", "200+"))
    keys = {t.key for t in templates}
    assert "debt_capital" in keys
    assert "accounts_receivable" in keys


def test_empresa_grande_revenue_muestra_avanzados():
    templates = build_kpi_templates(_buf("manufacturing", "11-50", "15M+"))
    keys = {t.key for t in templates}
    assert "debt_capital" in keys
    assert "accounts_receivable" in keys


def test_headcount_nunca_aparece_en_templates():
    for ind in ("manufacturing", "technology"):
        templates = build_kpi_templates(_buf(ind))
        keys = {t.key for t in templates}
        assert "headcount" not in keys


# ── Headcount auto-calculado ──────────────────────────────────────────────────

@pytest.mark.parametrize("emp_range,expected", [
    ("1-10", 5),
    ("11-50", 30),
    ("51-200", 100),
    ("200+", 300),
])
def test_headcount_desde_rango(emp_range, expected):
    buf = _buf(employees=emp_range)
    assert _get_headcount_from_buffer(buf) == expected


# ── Reglas de alerta ──────────────────────────────────────────────────────────

def test_alerta_top5_warning_50pct():
    tmpl = _KPI_MAP["top5_concentration"]
    msg, sev = _run_alert_rules(tmpl, 50.0)
    assert msg is not None
    assert sev == "warning"


def test_alerta_top5_critical_65pct():
    tmpl = _KPI_MAP["top5_concentration"]
    msg, sev = _run_alert_rules(tmpl, 65.0)
    assert sev == "critical"


def test_alerta_top5_sin_alerta_bajo_umbral():
    tmpl = _KPI_MAP["top5_concentration"]
    msg, sev = _run_alert_rules(tmpl, 30.0)
    assert msg is None


def test_alerta_debt_capital_critico():
    tmpl = _KPI_MAP["debt_capital"]
    msg, sev = _run_alert_rules(tmpl, 3.5)
    assert sev == "critical"
    assert "2x" in msg


def test_alerta_otif_warning_85():
    tmpl = _KPI_MAP["otif"]
    msg, sev = _run_alert_rules(tmpl, 85.0)
    assert sev == "warning"


def test_alerta_otif_critical_75():
    tmpl = _KPI_MAP["otif"]
    msg, sev = _run_alert_rules(tmpl, 75.0)
    assert sev == "critical"


def test_alerta_cash_flow_negativo():
    tmpl = _KPI_MAP["free_cash_flow"]
    msg, sev = _run_alert_rules(tmpl, -50000)
    assert sev == "critical"


def test_alerta_margen_muy_bajo():
    tmpl = _KPI_MAP["operating_margin"]
    msg, sev = _run_alert_rules(tmpl, 5.0)  # benchmark=15%, 5 < 7.5
    assert sev == "warning"


def test_sin_alerta_margen_ok():
    tmpl = _KPI_MAP["operating_margin"]
    msg, sev = _run_alert_rules(tmpl, 20.0)
    assert msg is None


def test_alerta_board_sessions_bajo():
    tmpl = _KPI_MAP["board_sessions_year"]
    msg, sev = _run_alert_rules(tmpl, 2)
    assert sev == "warning"
    assert "12" in msg


def test_alerta_quality_returns_alto():
    tmpl = _KPI_MAP["quality_returns"]
    msg, sev = _run_alert_rules(tmpl, 5.0)
    assert sev == "warning"


# ── process_kpi_values ────────────────────────────────────────────────────────

def test_process_agrega_headcount_automatico():
    buf = _buf("manufacturing", "11-50")
    templates = build_kpi_templates(buf)
    inp = _inputs(templates)
    results, _ = process_kpi_values(templates, inp, buf)
    keys = {r.key for r in results}
    assert "headcount" in keys
    headcount_result = next(r for r in results if r.key == "headcount")
    assert headcount_result.current_value == 30.0


def test_process_gap_cuando_unknown():
    buf = _buf("manufacturing")
    templates = build_kpi_templates(buf)
    # Marcar el primero como desconocido
    key = templates[0].key
    inp = [KPIValueInput(key=key, unknown=True)]
    results, _ = process_kpi_values(templates, inp, buf)
    gap = next(r for r in results if r.key == key)
    assert gap.is_gap is True


def test_process_alerta_aparece_en_lista():
    buf = _buf("manufacturing")
    templates = build_kpi_templates(buf)
    overrides = {"top5_concentration": {"current": 65.0}}
    inp = _inputs(templates, overrides)
    _, alerts = process_kpi_values(templates, inp, buf)
    assert any("top 5" in a.lower() or "concentración" in a.lower() for a in alerts)


def test_process_sin_alertas_valores_ok():
    buf = _buf("manufacturing", "1-10")
    templates = build_kpi_templates(buf)
    # Valores dentro de benchmarks para no disparar ninguna alerta
    safe_values = {
        "monthly_revenue": 500_000,
        "operating_margin": 20.0,
        "free_cash_flow": 50_000,
        "active_clients": 100,
        "top5_concentration": 25.0,   # <40 → sin alerta
        "sales_growth_yoy": 10.0,
        "capacity_utilization": 75.0,
        "quality_returns": 1.0,       # <2 → sin alerta
        "staff_turnover": 10.0,
        "board_sessions_year": 12.0,
        "agreements_met": 95.0,
    }
    overrides = {k: {"current": v} for k, v in safe_values.items()}
    inp = _inputs(templates, overrides)
    _, alerts = process_kpi_values(templates, inp, buf)
    assert len(alerts) == 0
