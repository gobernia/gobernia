from pydantic import BaseModel


class CoverageRow(BaseModel):
    key: str
    label: str
    type: str
    frecuencia_anual: int
    esperadas: int
    realizadas: int
    estado: str


class CoverageMarkIn(BaseModel):
    theme_key: str
    covered: bool
