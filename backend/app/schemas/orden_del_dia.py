from pydantic import BaseModel, Field

from app.schemas.annual_plan import ObjectiveOut


class ThemeRef(BaseModel):
    key: str
    label: str
    every_n_sessions: int | None = None


class OrdenDelDiaOut(BaseModel):
    month_index: int
    period_year: int
    period_month: int
    permanent_themes: list[ThemeRef] = Field(default_factory=list)
    coverage_themes: list[ThemeRef] = Field(default_factory=list)
    covered_keys: list[str] = Field(default_factory=list)
    objectives: list[ObjectiveOut] = Field(default_factory=list)
