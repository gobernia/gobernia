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


class BoardMonthOut(BaseModel):
    month_index:   int
    period_year:   int
    period_month:  int
    label:         str            # "Marzo 2026"
    es_mes_actual: bool
    tareas:        list[BoardTaskOut] = Field(default_factory=list)


class BoardOut(BaseModel):
    meses: list[BoardMonthOut] = Field(default_factory=list)
