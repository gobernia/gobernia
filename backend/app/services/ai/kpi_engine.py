"""
Motor de KPIs — Etapa 5.
Implementa las reglas del spec:
  - KPIs pre-filtrados por industria y prioridades
  - Benchmarks pre-llenados por industria
  - Condicionales: servicios oculta operacionales, >200 emp / >$15M activa avanzados
  - Alertas automáticas por umbral
"""
from app.schemas.etapa5 import KPIResult, KPITemplate, KPIValueInput

# ── Industrias de servicios (ocultan KPIs operacionales) ──────────────────────
_SERVICE_INDUSTRIES = {
    "professional_services", "health", "education", "technology", "other"
}

# ── Catálogo completo de KPIs del spec ────────────────────────────────────────
_ALL_KPIS: list[KPITemplate] = [
    # FINANZAS
    KPITemplate(key="monthly_revenue",   label="Ingresos mensuales",
                dimension="finance",     unit="MXN",
                benchmark=None,          benchmark_label="Meta definida por empresa",
                owner_agents=["CFO"]),
    KPITemplate(key="operating_margin",  label="Margen operativo",
                dimension="finance",     unit="%",
                benchmark=15.0,          benchmark_label="Benchmark industria ~15%",
                owner_agents=["CFO"]),
    KPITemplate(key="free_cash_flow",    label="Flujo de caja libre mensual",
                dimension="finance",     unit="MXN",
                benchmark=None,          benchmark_label="Positivo siempre",
                owner_agents=["CFO"]),
    KPITemplate(key="debt_capital",      label="Deuda total / Capital",
                dimension="finance",     unit="x",
                benchmark=2.0,           benchmark_label="Máximo 2x",
                owner_agents=["CFO", "CRO"], is_conditional=True),
    KPITemplate(key="accounts_receivable", label="Cuentas por cobrar",
                dimension="finance",     unit="días",
                benchmark=45.0,          benchmark_label="Benchmark industria ~45 días",
                owner_agents=["CFO"], is_conditional=True),
    # COMERCIAL
    KPITemplate(key="active_clients",    label="Clientes activos",
                dimension="commercial",  unit="#",
                benchmark=None,          benchmark_label="Crecimiento vs año anterior",
                owner_agents=["CSO"]),
    KPITemplate(key="top5_concentration", label="Concentración top 5 clientes",
                dimension="commercial",  unit="%",
                benchmark=40.0,          benchmark_label="Alerta si >40%",
                owner_agents=["CSO", "CRO"]),
    KPITemplate(key="sales_growth_yoy",  label="Crecimiento de ventas YoY",
                dimension="commercial",  unit="%",
                benchmark=None,          benchmark_label="Meta definida por empresa",
                owner_agents=["CSO", "CFO"]),
    # OPERACIONES (ocultos en servicios)
    KPITemplate(key="capacity_utilization", label="Capacidad utilizada",
                dimension="operations",  unit="%",
                benchmark=60.0,          benchmark_label="Mínimo 60%",
                owner_agents=["Auditor"], is_conditional=True),
    KPITemplate(key="otif",              label="OTIF / Entregas a tiempo",
                dimension="operations",  unit="%",
                benchmark=95.0,          benchmark_label="Mínimo 95%",
                owner_agents=["Auditor"], is_conditional=True),
    KPITemplate(key="quality_returns",   label="Devoluciones por calidad",
                dimension="operations",  unit="%",
                benchmark=2.0,           benchmark_label="Máximo 2%",
                owner_agents=["Auditor", "CRO"], is_conditional=True),
    # RH
    KPITemplate(key="staff_turnover",    label="Rotación de personal",
                dimension="hr",          unit="%",
                benchmark=15.0,          benchmark_label="Benchmark industria ~15%",
                owner_agents=["CSO"]),
    KPITemplate(key="headcount",         label="Headcount total",
                dimension="hr",          unit="#",
                benchmark=None,          benchmark_label="Auto-calculado",
                owner_agents=["CSO"]),
    # GOBIERNO
    KPITemplate(key="board_sessions_year", label="Sesiones de consejo / año",
                dimension="governance",  unit="#",
                benchmark=12.0,          benchmark_label="12 sesiones/año (mensual)",
                owner_agents=["Auditor"]),
    KPITemplate(key="agreements_met",    label="Acuerdos cumplidos",
                dimension="governance",  unit="%",
                benchmark=90.0,          benchmark_label="Mínimo 90%",
                owner_agents=["Auditor"]),
]

_KPI_MAP = {kpi.key: kpi for kpi in _ALL_KPIS}


def build_kpi_templates(memory_buffer: dict) -> list[KPITemplate]:
    """Retorna los KPIs visibles para esta empresa según industria y tamaño."""
    industry = memory_buffer.get("company", {}).get("industry", "")
    employees = memory_buffer.get("company", {}).get("employees", "")
    revenue = memory_buffer.get("company", {}).get("annual_revenue", "")

    is_service = industry in _SERVICE_INDUSTRIES
    is_advanced = employees == "200+" or revenue == "15M+"

    result: list[KPITemplate] = []
    for kpi in _ALL_KPIS:
        if kpi.key == "headcount":
            continue  # se auto-llena, no se muestra en el form
        if kpi.key in ("capacity_utilization", "otif", "quality_returns") and is_service:
            continue  # ocultos en industrias de servicios
        if kpi.key in ("debt_capital", "accounts_receivable") and not is_advanced:
            continue  # solo para empresas grandes
        if kpi.key == "otif" and not is_advanced and not is_service:
            continue  # OTIF solo para avanzados no-servicios
        result.append(kpi)

    return result


def _get_headcount_from_buffer(memory_buffer: dict) -> int | None:
    """Auto-calcula headcount desde el rango de Etapa 1."""
    emp_range = memory_buffer.get("company", {}).get("employees", "")
    mapping = {"1-10": 5, "11-50": 30, "51-200": 100, "200+": 300}
    return mapping.get(emp_range)


def _run_alert_rules(kpi: KPITemplate, value: float) -> tuple[str | None, str | None]:
    """Retorna (mensaje_alerta, severidad) o (None, None) si no hay alerta."""
    key = kpi.key

    if key == "top5_concentration" and value > 40:
        return (
            f"Concentración top 5 clientes al {value}% — riesgo comercial alto. "
            "El CRO Agent evaluará estrategias de diversificación.",
            "critical" if value > 60 else "warning",
        )
    if key == "debt_capital" and value > 2:
        return (
            f"Deuda/Capital en {value}x supera el límite recomendado de 2x. "
            "El CFO y CRO Agent priorizarán este punto en sesión.",
            "critical",
        )
    if key == "otif" and value < 90:
        return (
            f"OTIF al {value}% — por debajo del mínimo aceptable de 90%. "
            "El Auditor Agent analizará cuellos de botella operativos.",
            "critical" if value < 80 else "warning",
        )
    if key == "quality_returns" and value > 2:
        return (
            f"Devoluciones al {value}% superan el benchmark de 2%. "
            "Impacta margen y reputación.",
            "warning",
        )
    if key == "operating_margin" and kpi.benchmark and value < kpi.benchmark * 0.5:
        return (
            f"Margen operativo al {value}% — muy por debajo del benchmark ({kpi.benchmark}%). "
            "El CFO Agent revisará estructura de costos.",
            "warning",
        )
    if key == "free_cash_flow" and value < 0:
        return (
            "Flujo de caja libre negativo — riesgo de liquidez. "
            "El CFO Agent generará análisis urgente.",
            "critical",
        )
    if key == "board_sessions_year" and value < 4:
        return (
            f"Solo {int(value)} sesión(es) de consejo al año — mínimo recomendado: 12. "
            "El Auditor Agent señalará este gap de gobernanza.",
            "warning",
        )
    return None, None


def process_kpi_values(
    templates: list[KPITemplate],
    inputs: list[KPIValueInput],
    memory_buffer: dict,
) -> tuple[list[KPIResult], list[str]]:
    """
    Procesa los valores ingresados por el usuario, aplica alertas y
    auto-llena headcount desde Etapa 1.
    """
    values_map = {kpi.current_value: kpi for kpi in inputs}  # needed below
    input_map = {i.key: i for i in inputs}
    alerts: list[str] = []
    results: list[KPIResult] = []

    for tmpl in templates:
        inp = input_map.get(tmpl.key)
        current = inp.current_value if inp else None
        target = inp.target_value if inp else None
        unknown = inp.unknown if inp else False
        alert_msg, severity = None, None

        if current is not None and not unknown:
            alert_msg, severity = _run_alert_rules(tmpl, current)
            if alert_msg:
                alerts.append(alert_msg)

        results.append(KPIResult(
            key=tmpl.key, label=tmpl.label,
            dimension=tmpl.dimension, unit=tmpl.unit,
            current_value=current, target_value=target,
            benchmark=tmpl.benchmark, unknown=unknown,
            owner_agents=tmpl.owner_agents,
            alert=alert_msg, alert_severity=severity,
            is_gap=unknown or current is None,
        ))

    # Auto-añadir headcount (no estaba en el form)
    headcount = _get_headcount_from_buffer(memory_buffer)
    if headcount:
        results.append(KPIResult(
            key="headcount", label="Headcount total",
            dimension="hr", unit="#",
            current_value=float(headcount), target_value=None,
            benchmark=None, unknown=False,
            owner_agents=["CSO"], is_gap=False,
        ))

    return results, alerts


def build_etapa5_memory(
    results: list[KPIResult], alerts: list[str]
) -> dict:
    by_dimension: dict[str, list] = {}
    for r in results:
        by_dimension.setdefault(r.dimension, []).append(r.model_dump())

    return {
        "kpis": by_dimension,
        "kpi_alerts": [{"message": a} for a in alerts],
    }
