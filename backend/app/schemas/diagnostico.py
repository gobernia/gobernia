from pydantic import BaseModel


class DiagnosticoStatusOut(BaseModel):
    status: str
    fail_reason: str | None = None


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
