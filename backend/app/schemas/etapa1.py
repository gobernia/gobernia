from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import (
    BoardStatus,
    BranchCount,
    EmployeeRange,
    FamilyGeneration,
    IndustryType,
    RevenueRange,
    YearsOperating,
)


class Etapa1Input(BaseModel):
    # Bloque 1 — Identidad
    company_name: str = Field(min_length=2, max_length=200)
    industry: IndustryType
    industry_custom: str | None = Field(default=None, max_length=100)
    location_city: str = Field(min_length=2, max_length=100)
    location_state: str = Field(min_length=2, max_length=100)
    location_country: str = Field(default="México", max_length=100)

    # Bloque 2 — Tamaño y Etapa
    years_operating: YearsOperating
    employees: EmployeeRange
    annual_revenue: RevenueRange
    branches: BranchCount

    # Bloque 3 — Estructura y Gobernanza
    is_family_business: bool
    family_generation: FamilyGeneration | None = None
    has_family_protocol: bool | None = None
    has_board: BoardStatus

    # Bloque 4 — Datos para investigación (opcionales en el schema; obligatorios al generar diagnóstico)
    website: str | None = Field(default=None, max_length=300)
    competitors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_seed_fields(self) -> "Etapa1Input":
        if self.website is not None:
            self.website = self.website.strip() or None
        self.competitors = [c.strip() for c in self.competitors if c and c.strip()][:10]
        return self

    @model_validator(mode="after")
    def validate_family_fields(self) -> "Etapa1Input":
        if self.is_family_business:
            if self.family_generation is None:
                raise ValueError("family_generation es requerido cuando es empresa familiar")
            if self.has_family_protocol is None:
                raise ValueError("has_family_protocol es requerido cuando es empresa familiar")
        else:
            # Si no es familiar, limpiamos los campos condicionales
            self.family_generation = None
            self.has_family_protocol = None
        return self

    @model_validator(mode="after")
    def validate_industry_custom(self) -> "Etapa1Input":
        if self.industry == IndustryType.other and not self.industry_custom:
            raise ValueError("industry_custom es requerido cuando industry es 'other'")
        return self


class Etapa1Output(BaseModel):
    session_id: str
    completed_stages: list[int]
    activated_modules: list[str]
    next_stage: int
    summary: str
