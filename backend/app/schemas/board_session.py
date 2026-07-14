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

class Finding(BaseModel):
    texto: str
    fuente: str = ""          # "Estado de resultados, p. 4" — "" si no viene de un documento


class Alert(BaseModel):
    nivel: str = "ambar"      # rojo | ambar | verde
    texto: str
    fuente: str = ""


class AgentAnalysis(BaseModel):
    agent: str
    summary: str
    findings: list[Finding]
    alerts: list[Alert]
    recommendations: list[str]
    preguntas: list[str] = []


# ── Normalización de análisis (retrocompatibilidad) ───────────────────────────
# Las sesiones guardadas antes del board pack tienen findings/alerts como
# list[str]. La API siempre entrega el shape nuevo; nada se migra en la BD.

VALID_ALERT_LEVELS = {"rojo", "ambar", "verde"}


def _norm_finding(f) -> dict | None:
    if isinstance(f, dict):
        texto = str(f.get("texto") or f.get("text") or "").strip()
        if not texto:
            return None
        return {"texto": texto, "fuente": str(f.get("fuente") or "")}
    texto = str(f or "").strip()
    return {"texto": texto, "fuente": ""} if texto else None


def _norm_alert(a) -> dict | None:
    if isinstance(a, dict):
        texto = str(a.get("texto") or a.get("text") or "").strip()
        if not texto:
            return None
        nivel = str(a.get("nivel") or "").strip().lower()
        if nivel not in VALID_ALERT_LEVELS:
            nivel = "ambar"
        return {"nivel": nivel, "texto": texto, "fuente": str(a.get("fuente") or "")}
    texto = str(a or "").strip()
    return {"nivel": "ambar", "texto": texto, "fuente": ""} if texto else None


def normalize_analysis(analysis: dict | None) -> dict:
    """Lleva un análisis (nuevo o legacy) al shape nuevo, preservando claves extra."""
    a = dict(analysis or {})
    a["summary"] = str(a.get("summary") or "")
    a["findings"] = [f for f in (_norm_finding(x) for x in (a.get("findings") or [])) if f]
    a["alerts"] = [x for x in (_norm_alert(y) for y in (a.get("alerts") or [])) if x]
    a["recommendations"] = [str(r) for r in (a.get("recommendations") or []) if str(r).strip()]
    a["preguntas"] = [str(p) for p in (a.get("preguntas") or []) if str(p).strip()]
    return a


def normalize_agent_analyses(analyses: dict | None) -> dict | None:
    """Normaliza el dict {agente: análisis} completo de una BoardSession."""
    if not analyses:
        return analyses
    return {
        agent: (normalize_analysis(a) if isinstance(a, dict) else a)
        for agent, a in analyses.items()
    }


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


# ── Board pack (documentos de la sesión) ──────────────────────────────────────

class BoardDocumentOut(BaseModel):
    id: str
    filename: str
    document_type: str
    document_type_label: str
    created_at: datetime | None = None


class BoardDocumentList(BaseModel):
    items: list[BoardDocumentOut]


# ── Trigger de análisis ───────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    agents: list[str] = Field(
        default=["CFO", "CSO", "CRO", "Auditor"],
        description="Agentes a ejecutar. Por defecto los 4.",
    )
