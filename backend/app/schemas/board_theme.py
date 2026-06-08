from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

ThemeType = Literal["permanente", "cobertura", "emergente"]
VALID_FREQ = {1, 2, 3, 6, 12}


class BoardThemeOut(BaseModel):
    id: str
    key: str
    label: str
    type: str
    every_n_sessions: int | None = None
    active: bool
    is_default: bool
    order_index: int


class BoardThemeCreate(BaseModel):
    label: str
    type: ThemeType
    every_n_sessions: int | None = None

    @model_validator(mode="after")
    def _normalize_freq(self):
        if self.type == "permanente":
            self.every_n_sessions = 1
        elif self.type == "emergente":
            self.every_n_sessions = None
        elif self.every_n_sessions not in VALID_FREQ:
            raise ValueError("every_n_sessions debe ser 1, 2, 3, 6 o 12")
        return self


class BoardThemeUpdate(BaseModel):
    label: str | None = None
    every_n_sessions: int | None = None
    active: bool | None = None
    order_index: int | None = None

    @field_validator("every_n_sessions")
    @classmethod
    def _check_freq(cls, v):
        if v is not None and v not in VALID_FREQ:
            raise ValueError("every_n_sessions debe ser 1, 2, 3, 6 o 12")
        return v
