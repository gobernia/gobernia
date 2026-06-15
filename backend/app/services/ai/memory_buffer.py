"""
Servicio central del Memory Buffer.
Responsable de evaluar los condicionales del spec y ensamblar
el contexto que reciben los agentes de IA en cada etapa.
"""
from app.schemas.enums import BranchCount, EmployeeRange, RevenueRange
from app.schemas.etapa1 import Etapa1Input


def evaluate_etapa1_modules(data: Etapa1Input) -> list[str]:
    """
    Evalúa los condicionales de Etapa 1 del spec y retorna
    la lista de módulos activados que afectan etapas posteriores.

    Condicionales del spec:
    - empresa familiar → activa módulo familiar en Etapas 4 y 6
    - >200 empleados O >$15M ingresos → métricas avanzadas en Etapa 5
    - sin consejo → aumenta peso Auditor + CRO en primera sesión
    - 6+ sucursales → preguntas de control multi-sitio en Etapa 4
    """
    modules: list[str] = []

    if data.is_family_business:
        modules.append("family")

    if data.branches == BranchCount.six_plus:
        modules.append("multi_site")

    advanced = (
        data.employees == EmployeeRange.large or
        data.annual_revenue == RevenueRange.plus_15m
    )
    if advanced:
        modules.append("advanced_metrics")

    return modules


def build_etapa1_memory(data: Etapa1Input, activated_modules: list[str]) -> dict:
    """
    Construye el fragmento del Memory Buffer correspondiente a Etapa 1.
    Se fusiona con el buffer existente en la DB.
    """
    return {
        "company": {
            "name": data.company_name,
            "industry": data.industry.value,
            "industry_custom": data.industry_custom,
            "location": {
                "city": data.location_city,
                "state": data.location_state,
                "country": data.location_country,
            },
            "years_operating": data.years_operating.value,
            "employees": data.employees.value,
            "annual_revenue": data.annual_revenue.value,
            "branches": data.branches.value,
            "is_family_business": data.is_family_business,
            "family_generation": data.family_generation.value if data.family_generation else None,
            "has_family_protocol": data.has_family_protocol,
            "has_board": data.has_board.value,
            "website": data.website,
            "competitors": data.competitors,
        },
        "activated_modules": activated_modules,
    }


def build_company_narrative(data: Etapa1Input, activated_modules: list[str]) -> str:
    """
    Genera el resumen narrativo de la empresa que reciben los agentes de IA.
    Se actualiza al completar cada etapa.
    """
    family_note = (
        f" Es una empresa familiar de {data.family_generation.value} generación."
        if data.is_family_business and data.family_generation else ""
    )
    board_note = {
        "yes": "Cuenta con consejo formal.",
        "no": "No tiene consejo formal.",
        "in_progress": "Está en proceso de formar un consejo.",
    }.get(data.has_board.value, "")

    modules_note = ""
    if "multi_site" in activated_modules:
        modules_note += " Opera en múltiples ubicaciones (6+)."
    if "advanced_metrics" in activated_modules:
        modules_note += " Empresa de tamaño mediano-grande con métricas avanzadas activadas."

    return (
        f"{data.company_name} es una empresa del sector {data.industry.value} "
        f"ubicada en {data.location_city}, {data.location_state}. "
        f"Tiene {data.years_operating.value} años de operación, "
        f"{data.employees.value} empleados e ingresos anuales de {data.annual_revenue.value} USD."
        f"{family_note} {board_note}{modules_note}"
    ).strip()
