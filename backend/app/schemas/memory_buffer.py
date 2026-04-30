"""
Memory Buffer — fuente de verdad que alimenta a los 4 agentes de IA.
Se construye incrementalmente a medida que el usuario completa cada etapa.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.enums import (
    AgentTone,
    AgentType,
    BoardStatus,
    BranchCount,
    CentralizationLevel,
    ChallengeType,
    DiagnosticResponse,
    DirectiveRole,
    DocumentType,
    EmployeeRange,
    ExpectationType,
    FamilyGeneration,
    FunctionalArea,
    GovernanceLevel,
    IndustryType,
    ProcessingStatus,
    RevenueRange,
    SessionFrequency,
    YearsOperating,
)


# ── ETAPA 1 ───────────────────────────────────────────────────────────────────

class CompanyLocation(BaseModel):
    city: str
    state: str
    country: str = "México"


class Stage1Company(BaseModel):
    name: str
    industry: IndustryType
    location: CompanyLocation
    years_operating: YearsOperating
    employees: EmployeeRange
    annual_revenue: RevenueRange
    branches: BranchCount
    is_family_business: bool
    family_generation: FamilyGeneration | None = None
    has_family_protocol: bool | None = None
    has_board: BoardStatus


# ── ETAPA 2 ───────────────────────────────────────────────────────────────────

class TeamMember(BaseModel):
    name: str
    role: DirectiveRole
    role_custom: str | None = None
    is_family: bool = False
    makes_key_decisions: bool
    email: EmailStr


class TeamInferences(BaseModel):
    centralization_level: CentralizationLevel
    functional_gaps: list[FunctionalArea]
    family_concentration: float = Field(ge=0, le=100)
    continuity_risk: bool


# ── ETAPA 3 ───────────────────────────────────────────────────────────────────

class Priority(BaseModel):
    challenge: ChallengeType
    challenge_custom: str | None = None
    rank: int = Field(ge=1, le=5)
    lead_agent: AgentType
    activated_areas: list[FunctionalArea]


# ── ETAPA 4 ───────────────────────────────────────────────────────────────────

class DiagnosticItem(BaseModel):
    area: FunctionalArea
    question: str
    response: DiagnosticResponse
    is_conditional: bool = False


class MatrixFactor(BaseModel):
    description: str
    weight: float = Field(ge=0, le=1)
    rating: int = Field(ge=1, le=4)
    weighted_score: float


class SwotStrategies(BaseModel):
    offensive: list[str]    # F+O
    improvement: list[str]  # D+O
    defensive: list[str]    # F+A
    survival: list[str]     # D+A


class Matrices(BaseModel):
    mefi: dict[str, list[MatrixFactor]]  # {"strengths": [...], "weaknesses": [...]}
    mefe: dict[str, list[MatrixFactor]]  # {"opportunities": [...], "threats": [...]}
    swot: SwotStrategies
    business_summary: str


# ── ETAPA 5 ───────────────────────────────────────────────────────────────────

class KPIEntry(BaseModel):
    key: str
    label: str
    current_value: float | str | None = None
    target_value: float | str | None = None
    benchmark: float | str | None = None
    unknown: bool = False
    owner_agent: AgentType
    alert: str | None = None


class KPIAlerts(BaseModel):
    agent: AgentType
    kpi_key: str
    message: str
    severity: str  # "warning" | "critical"


class Stage5KPIs(BaseModel):
    finance: list[KPIEntry] = []
    commercial: list[KPIEntry] = []
    operations: list[KPIEntry] = []
    hr: list[KPIEntry] = []
    governance: list[KPIEntry] = []
    alerts: list[KPIAlerts] = []


# ── ETAPA 6 ───────────────────────────────────────────────────────────────────

class GovernanceChecklistItem(BaseModel):
    key: str
    question: str
    response: str  # "yes" | "no" | "in_progress" | "unknown"
    weight: int    # 1 (normal), 2 (medio), 3 (alto)
    owner_agent: AgentType
    is_family_item: bool = False


class Stage6Governance(BaseModel):
    checklist: list[GovernanceChecklistItem]
    score: float = Field(ge=0, le=100)
    level: GovernanceLevel


# ── ETAPA 7 ───────────────────────────────────────────────────────────────────

class DocumentRecord(BaseModel):
    id: uuid.UUID
    document_type: DocumentType
    filename: str
    s3_key: str
    processing_status: ProcessingStatus = ProcessingStatus.pending
    agent_insights: dict[str, list[str]] | None = None


# ── ETAPA 8 ───────────────────────────────────────────────────────────────────

class Stage8Vision(BaseModel):
    three_year_view: str
    year_one_goal: str
    council_expectations: list[ExpectationType]
    session_frequency: SessionFrequency
    agent_tone: AgentTone


# ── BSC SNAPSHOT ──────────────────────────────────────────────────────────────

class BSCDimension(BaseModel):
    name: str
    owner_agent: AgentType
    health_score: float = Field(ge=0, le=100)
    kpis: list[KPIEntry]


class BSCSnapshot(BaseModel):
    finance: BSCDimension
    commercial: BSCDimension
    operations: BSCDimension
    talent: BSCDimension
    governance: BSCDimension
    generated_at: datetime


# ── AI CONTEXT ────────────────────────────────────────────────────────────────

class AgentPersonality(BaseModel):
    agent: AgentType
    tone: AgentTone
    priority_areas: list[FunctionalArea]
    lead_this_session: bool


class AIContext(BaseModel):
    company_narrative: str
    activated_modules: list[str]  # ["family", "multi_site", "advanced_metrics"]
    lead_agent: AgentType
    agent_personalities: dict[str, AgentPersonality]
    bsc_snapshot: BSCSnapshot | None = None


# ── MEMORY BUFFER COMPLETO ────────────────────────────────────────────────────

class GoberniaMemoryBuffer(BaseModel):
    session_id: uuid.UUID
    user_id: str
    completed_stages: list[int] = []

    # Etapas
    company: Stage1Company | None = None
    team: list[TeamMember] = []
    team_inferences: TeamInferences | None = None
    priorities: list[Priority] = []
    diagnostic_responses: list[DiagnosticItem] = []
    matrices: Matrices | None = None
    kpis: Stage5KPIs | None = None
    governance: Stage6Governance | None = None
    documents: list[DocumentRecord] = []
    vision: Stage8Vision | None = None

    # Contexto IA (se recalcula al completar cada etapa)
    ai_context: AIContext | None = None

    # Meta
    onboarding_started_at: datetime
    onboarding_completed_at: datetime | None = None
