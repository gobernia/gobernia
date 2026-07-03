from pydantic import BaseModel


class ToddTurnIn(BaseModel):
    answer: str | None = None


class ToddTurnOut(BaseModel):
    message: str
    options: list[str] | None = None
    input: str = "text"
    done: bool = False
    areas_cubiertas: list[str] = []
    expects_detail: bool = False


class ToddMessage(BaseModel):
    role: str
    text: str
    options: list[str] | None = None


class ToddSessionOut(BaseModel):
    status: str
    messages: list[ToddMessage]
    done: bool
    areas_cubiertas: list[str] = []


class ToddEditIn(BaseModel):
    answer_index: int
    nueva_respuesta: str


class ToddMetasOut(BaseModel):
    metas: list[str]


class ToddMetasIn(BaseModel):
    orden: list[str]


class FodaOut(BaseModel):
    status: str
    foda: dict | None = None
    metas: list[str] = []
    factores_externos: dict = {}
