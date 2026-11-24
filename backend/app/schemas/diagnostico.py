from pydantic import BaseModel


class DiagnosticoStatusOut(BaseModel):
    status: str
    fail_reason: str | None = None
    segundos: int | None = None  # cuánto lleva generándose (para el reloj de la pantalla de espera)


class DiagnosticoSection(BaseModel):
    key: str
    title: str
    body: str


class DiagnosticoSource(BaseModel):
    title: str
    url: str


class DiagnosticoOut(BaseModel):
    status: str
    fail_reason: str | None = None
    sections: list[DiagnosticoSection] = []
    sources: list[DiagnosticoSource] = []
    fortalezas_debilidades: dict = {}
    riesgos: list = []
