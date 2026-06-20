from pydantic import BaseModel


class ToddTurnIn(BaseModel):
    answer: str | None = None


class ToddTurnOut(BaseModel):
    message: str
    options: list[str] | None = None
    input: str = "text"
    done: bool = False


class ToddMessage(BaseModel):
    role: str
    text: str
    options: list[str] | None = None


class ToddSessionOut(BaseModel):
    status: str
    messages: list[ToddMessage]
    done: bool
