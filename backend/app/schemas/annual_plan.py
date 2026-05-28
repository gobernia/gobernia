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
    months:              list[MonthlyPlanOut] = Field(default_factory=list)


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
