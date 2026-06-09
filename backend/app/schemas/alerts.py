from pydantic import BaseModel


class AlertItem(BaseModel):
    level: str
    category: str
    message: str
