from pydantic import BaseModel


class MinutaDecision(BaseModel):
    pregunta: str
    opcion_a: str
    opcion_b: str
    decision_tomada: str | None = None


class MinutaCompromiso(BaseModel):
    descripcion: str
    fecha: str


class MinutaTema(BaseModel):
    id: int
    titulo: str
    sintesis: str
    decision: MinutaDecision
    compromiso: MinutaCompromiso | None = None


class MinutaOut(BaseModel):
    generada: bool
    carta: str
    temas: list[MinutaTema]


class DecisionIn(BaseModel):
    tema_id: int
    decision: str
