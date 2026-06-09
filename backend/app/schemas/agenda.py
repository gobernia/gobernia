from pydantic import BaseModel


class AgendaItem(BaseModel):
    orden: int
    titulo: str
    area: str
    detector: str
    impacto: str
    urgencia: str
    racional: str
    evidencia: list[str]
    score: float


class AgendaOut(BaseModel):
    curada: bool
    carta: str
    items: list[AgendaItem]
