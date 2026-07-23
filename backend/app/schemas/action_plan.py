from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


TaskStatus   = Literal["pendiente", "en_progreso", "completada"]
TaskPriority = Literal["alta", "media", "baja"]


class ActionTaskBase(BaseModel):
    title:        str
    description:  str | None = None
    source_agent: str | None = None
    status:       TaskStatus = "pendiente"
    priority:     TaskPriority = "media"
    owner:        str | None = None
    due_date:     date | None = None
    tags:         list[str] = Field(default_factory=list)
    order_index:  int = 0


class ActionTaskCreate(BaseModel):
    title:        str
    description:  str | None = None
    source_agent: str | None = None
    status:       TaskStatus = "pendiente"
    priority:     TaskPriority = "media"
    owner:        str | None = None
    due_date:     date | None = None
    tags:         list[str] = Field(default_factory=list)


class AdaptarTareaIn(BaseModel):
    feedback: str = Field(min_length=1, max_length=1000)


class AdaptarTareaOut(BaseModel):
    nueva_tarea: str
    descripcion: str
    por_que: str


class TaskEstadoUpdate(BaseModel):
    # str (no Literal) para validar a mano y devolver 400 en estado inválido,
    # como pide el tablero. El candado de evidencia NO aplica a esta vía.
    status: str


class ActionTaskUpdate(BaseModel):
    title:        str | None = None
    description:  str | None = None
    status:       TaskStatus | None = None
    priority:     TaskPriority | None = None
    owner:        str | None = None
    due_date:     date | None = None
    tags:         list[str] | None = None
    order_index:  int | None = None


class ActionTaskOut(ActionTaskBase):
    id:           str
    plan_id:      str | None = None
    objective_id: str | None = None
    kpi_ref:      str | None = None
    created_at:   datetime
    updated_at:   datetime
    evidence_count: int = 0
    required_doc: str | None = None
    explicacion: dict | None = None


class ActionPlanOut(BaseModel):
    id:               str
    board_session_id: str
    title:            str
    created_at:       datetime
    updated_at:       datetime
    tasks:            list[ActionTaskOut]


class GeneratePlanResponse(BaseModel):
    plan_id:    str
    task_count: int
    plan:       ActionPlanOut
