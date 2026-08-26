"""Tablero operativo (tipo Monday) del plan anual — todas las tareas agrupadas por mes."""
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.action_plan import TaskPriority, TaskStatus


class BoardTaskOut(BaseModel):
    id:        str
    title:     str
    owner:     str | None = None
    owner_email: str | None = None
    status:    TaskStatus
    priority:  TaskPriority
    due_date:  date | None = None
    objetivo:  str | None = None   # title del Objective padre
    # Mes de origen cuando la tarea se arrastra a otro mes (p.ej. "Marzo 2026").
    # None para las tareas propias del mes.
    viene_de:  str | None = None
    # Índice del pilar del roadmap que la tarea hace avanzar (None si no se determinó).
    pilar_index: int | None = None
    # False = quedó FUERA del Plan anual aprobado (pendiente sin ejecutar).
    incluida: bool = True
    # ── Agenda de gobierno: cada tarea es un punto del Orden del Día ──
    # Consejero IA que lidera el análisis del punto (CFO|CSO|CRO|Auditor).
    lead_agent: str | None = None
    # informacion | seguimiento | deliberacion | decision.
    agenda_type: str | None = None
    # Decisión/recomendación esperada de la sesión, si aplica.
    decision_expected: str | None = None
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
    # Tareas que quedaron FUERA del plan del año (incluida=False): visibles como
    # pendientes para activarlas después o eliminarlas.
    pendientes: list[BoardTaskOut] = Field(default_factory=list)
