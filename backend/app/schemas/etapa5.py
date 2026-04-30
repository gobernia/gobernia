from pydantic import BaseModel, Field


class KPITemplate(BaseModel):
    """KPI vacío con benchmark pre-llenado que el frontend muestra al usuario."""
    key: str
    label: str
    dimension: str          # finance, commercial, operations, hr, governance
    unit: str               # %, MXN, días, #, x
    benchmark: float | None
    benchmark_label: str | None
    owner_agents: list[str]
    is_conditional: bool = False


class KPIValueInput(BaseModel):
    key: str
    current_value: float | None = None
    target_value: float | None = None
    unknown: bool = False   # true = "No lo sé" → el agente lo marca como gap


class Etapa5Input(BaseModel):
    kpis: list[KPIValueInput] = Field(min_length=1)


class KPIResult(BaseModel):
    key: str
    label: str
    dimension: str
    unit: str
    current_value: float | None
    target_value: float | None
    benchmark: float | None
    unknown: bool
    owner_agents: list[str]
    alert: str | None = None
    alert_severity: str | None = None  # "warning" | "critical"
    is_gap: bool = False


class Etapa5KPIsOutput(BaseModel):
    session_id: str
    kpi_templates: list[KPITemplate]
    total_kpis: int
    headcount_auto: int | None


class Etapa5Output(BaseModel):
    session_id: str
    completed_stages: list[int]
    kpi_results: list[KPIResult]
    alerts: list[str]
    gap_count: int
    next_stage: int
