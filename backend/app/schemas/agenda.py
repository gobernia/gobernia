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
