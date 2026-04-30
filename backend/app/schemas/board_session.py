from datetime import datetime
from pydantic import BaseModel, Field


# ── Creación de sesión ────────────────────────────────────────────────────────

class BoardSessionCreate(BaseModel):
    period_year: int = Field(ge=2020, le=2100)
    period_month: int = Field(ge=1, le=12)


# ── KPIs del periodo ──────────────────────────────────────────────────────────

class PeriodKPIInput(BaseModel):
    key: str
    current_value: float | None = None
    target_value: float | None = None
    unknown: bool = False


class BoardSessionKPIsInput(BaseModel):
    kpis: list[PeriodKPIInput] = Field(min_length=1)


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessageInput(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    agent: str | None = None   # Si None, el sistema decide qué agente responde


class ChatMessageOut(BaseModel):
    message_id: str
    role: str
    agent: str | None
    content: str
    created_at: datetime


# ── Respuestas de sesión ──────────────────────────────────────────────────────

class AgentAnalysis(BaseModel):
    agent: str
    summary: str
    findings: list[str]
    alerts: list[str]
    recommendations: list[str]


class BoardSessionSummary(BaseModel):
    board_session_id: str
    onboarding_session_id: str
    period_year: int
    period_month: int
    period_label: str          # "Abril 2025"
    status: str
    governance_score_snapshot: float | None
    document_count: int
    message_count: int
    created_at: datetime


class BoardSessionDetail(BaseModel):
    board_session_id: str
    onboarding_session_id: str
    period_year: int
    period_month: int
    period_label: str
    status: str
    kpi_snapshot: dict | None
    agent_analyses: dict | None
    governance_score_snapshot: float | None
    messages: list[ChatMessageOut]
    created_at: datetime
    completed_at: datetime | None


# ── Trigger de análisis ───────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    agents: list[str] = Field(
        default=["CFO", "CSO", "CRO", "Auditor"],
        description="Agentes a ejecutar. Por defecto los 4.",
    )
