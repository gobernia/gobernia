from pydantic import BaseModel, Field


class GovernanceItem(BaseModel):
    key: str
    label: str
    description: str
    dimension: str       # board, compliance, documentation, family
    weight: float
    is_conditional: bool = False   # True = solo empresas familiares


class GovernanceItemInput(BaseModel):
    key: str
    response: str        # "yes" | "partial" | "no" | "na"


class Etapa6Input(BaseModel):
    items: list[GovernanceItemInput] = Field(min_length=1)


class GovernanceDimensionScore(BaseModel):
    dimension: str
    label: str
    score: float          # 0-100
    earned: float
    possible: float
    items_compliant: int
    items_evaluated: int


class Etapa6ItemsOutput(BaseModel):
    session_id: str
    items: list[GovernanceItem]
    total_items: int
    includes_family: bool


class Etapa6Output(BaseModel):
    session_id: str
    completed_stages: list[int]
    governance_score: float        # 0-100 normalizado
    governance_level: str          # Inicial | En desarrollo | Consolidado | Excelente
    dimension_scores: list[GovernanceDimensionScore]
    gaps: list[str]                # labels de ítems con "no"
    recommendations: list[str]
    next_stage: int
