from datetime import date

from pydantic import BaseModel, Field

from app.schemas.action_plan import ActionTaskOut, TaskPriority, TaskStatus


class ObjectiveOut(BaseModel):
    id:          str
    title:       str
    description: str | None = None
    kpi_refs:    list[str] = Field(default_factory=list)
    order_index: int = 0
    tasks:       list[ActionTaskOut] = Field(default_factory=list)


class MonthlyPlanOut(BaseModel):
    id:           str
    month_index:  int
    period_year:  int
    period_month: int
    focus:        str | None = None
    status:       str
    review:       dict | None = None
    objectives:   list[ObjectiveOut] = Field(default_factory=list)


class AnnualPlanOut(BaseModel):
    id:                  str
    title:               str
    start_date:          date
    status:              str
    diagnostico_summary: str | None = None
    genesis_session_id:  str | None = None
    horizon_years:       int = 3
    milestones:          dict | None = None
    months:              list[MonthlyPlanOut] = Field(default_factory=list)


class GeneratePlanRequest(BaseModel):
    horizon_years: int = Field(default=3, ge=1, le=3)


class AnnualPlanStatusOut(BaseModel):
    status:             str            # generating | active | failed | completed
    active_month_index: int | None = None


# ── Edición ───────────────────────────────────────────────────────────────────

class ObjectiveCreate(BaseModel):
    monthly_plan_id: str
    title:           str
    description:     str | None = None
    kpi_refs:        list[str] = Field(default_factory=list)


class ObjectiveUpdate(BaseModel):
    title:       str | None = None
    description: str | None = None
    kpi_refs:    list[str] | None = None
    order_index: int | None = None


class AnnualTaskCreate(BaseModel):
    objective_id: str
    title:        str
    description:  str | None = None
    status:       TaskStatus = "pendiente"
    priority:     TaskPriority = "media"
    owner:        str | None = None
    due_date:     date | None = None
    kpi_ref:      str | None = None
    tags:         list[str] = Field(default_factory=list)


class CloseMonthRequest(BaseModel):
    kpis: dict[str, float] = Field(default_factory=dict)


class ApplyProposalRequest(BaseModel):
    proposal_id: str


class CloseMonthResponse(BaseModel):
    month:              MonthlyPlanOut
    active_month_index: int


# ── Plan anual (prioridades aprobadas del roadmap) ────────────────────────────

class PilarAnualOut(BaseModel):
    """Un pilar del roadmap, con su índice, para elegirlo/mostrarlo en el plan anual."""
    indice:      int
    nombre:      str | None = None
    descripcion: str | None = None
    razon:       str | None = None
    objetivo:    str | None = None
    kpis:        list[dict] = Field(default_factory=list)
    estrategias: list = Field(default_factory=list)
    riesgos:     list = Field(default_factory=list)


class PlanAnualOut(BaseModel):
    anio:                int
    aprobado:            bool
    aprobado_at:         str | None = None
    # Los pilares del roadmap (con índice), para elegir.
    pilares_disponibles: list[PilarAnualOut] = Field(default_factory=list)
    # Los guardados en plan_anual (o [] si no está aprobado).
    pilares_aprobados:   list[PilarAnualOut] = Field(default_factory=list)


class AprobarPlanAnualIn(BaseModel):
    indices: list[int]
