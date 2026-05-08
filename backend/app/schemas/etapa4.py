from enum import Enum

from pydantic import BaseModel, Field


class InternalResponse(str, Enum):
    yes = "yes"
    partial = "partial"
    no = "no"


class ExternalResponse(str, Enum):
    yes = "yes"
    partial = "partial"
    no = "no"
    unknown = "unknown"


class DiagnosticQuestion(BaseModel):
    question_id: str
    area: str
    text: str
    description: str = ""
    is_base: bool = False
    is_external: bool = False
    is_conditional: bool = False
    response_options: list[str]


class DiagnosticResponseInput(BaseModel):
    question_id: str
    response: str


class Etapa4Input(BaseModel):
    responses: list[DiagnosticResponseInput] = Field(min_length=1)


class MatrixFactor(BaseModel):
    description: str
    area: str
    weight: float
    rating: int           # 1-4
    weighted_score: float


class SwotStrategies(BaseModel):
    offensive: list[str]      # F+O
    improvement: list[str]    # D+O
    defensive: list[str]      # F+A
    survival: list[str]       # D+A


class DiagnosticMatrices(BaseModel):
    mefi: dict[str, list[MatrixFactor]]   # strengths / weaknesses
    mefe: dict[str, list[MatrixFactor]]   # opportunities / threats
    swot: SwotStrategies
    business_summary: str
    strength_count: int
    weakness_count: int


class Etapa4QuestionsOutput(BaseModel):
    session_id: str
    questions: list[DiagnosticQuestion]
    total_questions: int


class Etapa4Output(BaseModel):
    session_id: str
    completed_stages: list[int]
    matrices: DiagnosticMatrices
    next_stage: int
