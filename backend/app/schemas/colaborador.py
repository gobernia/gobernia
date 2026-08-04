from pydantic import BaseModel


class ColaboradorLinkIn(BaseModel):
    email: str
    nombre: str | None = None


class ColaboradorLinkOut(BaseModel):
    token: str


class TareaColabOut(BaseModel):
    id: str
    title: str
    description: str | None
    status: str
    due_date: str | None
    objetivo: str | None
    explicacion: dict | None
    tiene_explicacion: bool


class EscritorioOut(BaseModel):
    nombre: str | None
    empresa: str | None
    tareas: list[TareaColabOut]


class ToddMsgIn(BaseModel):
    mensaje: str


class ToddChatOut(BaseModel):
    mensajes: list[dict]


class ToddReplyOut(BaseModel):
    reply: str
    mensajes: list[dict]
