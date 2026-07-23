"""Tablero operativo (tipo Monday) del plan anual — todas las tareas agrupadas por mes."""
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.action_plan import TaskPriority, TaskStatus


class BoardTaskOut(BaseModel):
    id:        str
    title:     str
    owner:     str | None = None
    status:    TaskStatus
    priority:  TaskPriority
    due_date:  date | None = None
    objetivo:  str | None = None   # title del Objective padre
    # Mes de origen cuando la tarea se arrastra a otro mes (p.ej. "Marzo 2026").
    # None para las tareas propias del mes.
    viene_de:  str | None = None
    # Cuántas evidencias tiene subidas la tarea.
    evidencias: int = 0
    # Veredicto del Consejo sobre la evidencia: {"estado", "motivo"} o None si nunca se validó.
    validacion: dict | None = None


class BoardMonthOut(BaseModel):
    month_index:   int
    period_year:   int
    period_month:  int
    label:         str            # "Marzo 2026"
    es_mes_actual: bool
    tareas:        list[BoardTaskOut] = Field(default_factory=list)
    # Tareas incompletas de meses anteriores, arrastradas a la vista del mes actual.
    # Vacía para todos los meses salvo el mes actual (y solo si hay atrasos).
    arrastradas:   list[BoardTaskOut] = Field(default_factory=list)


class BoardOut(BaseModel):
    meses: list[BoardMonthOut] = Field(default_factory=list)
