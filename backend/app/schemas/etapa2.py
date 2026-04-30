from pydantic import BaseModel, EmailStr, Field, model_validator

from app.schemas.enums import CentralizationLevel, DirectiveRole, FunctionalArea


class TeamMemberInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    role: DirectiveRole
    role_custom: str | None = Field(default=None, max_length=100)
    is_family: bool = False
    makes_key_decisions: bool
    email: EmailStr | None = None

    @model_validator(mode="after")
    def validate_role_custom(self) -> "TeamMemberInput":
        if self.role == DirectiveRole.other and not self.role_custom:
            raise ValueError("role_custom es requerido cuando role es 'other'")
        return self


class Etapa2Input(BaseModel):
    team: list[TeamMemberInput] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def at_least_one_decision_maker(self) -> "Etapa2Input":
        if not any(m.makes_key_decisions for m in self.team):
            raise ValueError("Al menos un miembro debe tomar decisiones clave")
        return self


class TeamInferencesOutput(BaseModel):
    centralization_level: CentralizationLevel
    functional_gaps: list[FunctionalArea]
    family_concentration: float
    continuity_risk: bool
    alerts: list[str]


class Etapa2Output(BaseModel):
    session_id: str
    completed_stages: list[int]
    team_count: int
    inferences: TeamInferencesOutput
    next_stage: int
