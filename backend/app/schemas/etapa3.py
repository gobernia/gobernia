from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import AgentType, ChallengeType, FunctionalArea


class PriorityInput(BaseModel):
    challenge: ChallengeType
    challenge_custom: str | None = Field(default=None, max_length=150)
    rank: int = Field(ge=1, le=5)

    @model_validator(mode="after")
    def validate_custom(self) -> "PriorityInput":
        if self.challenge == ChallengeType.other and not self.challenge_custom:
            raise ValueError("challenge_custom es requerido cuando challenge es 'other'")
        return self


class Etapa3Input(BaseModel):
    priorities: list[PriorityInput] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def validate_ranks(self) -> "Etapa3Input":
        ranks = [p.rank for p in self.priorities]
        # Ranks deben ser únicos y consecutivos desde 1
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise ValueError("Los ranks deben ser únicos y consecutivos (1, 2, 3...)")
        # No se puede repetir el mismo reto
        challenges = [p.challenge for p in self.priorities]
        if len(challenges) != len(set(challenges)):
            raise ValueError("No se pueden repetir retos")
        return self


class PriorityMapped(BaseModel):
    challenge: ChallengeType
    challenge_custom: str | None
    rank: int
    lead_agent: AgentType
    supporting_agents: list[AgentType]
    activated_areas: list[FunctionalArea]


class Etapa3Output(BaseModel):
    session_id: str
    completed_stages: list[int]
    lead_agent: AgentType           # agente líder determinado por prioridad #1
    priorities_mapped: list[PriorityMapped]
    next_stage: int
