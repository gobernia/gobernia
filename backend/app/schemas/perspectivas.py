from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Role = Literal["empleado", "directivo", "socio", "cliente", "proveedor"]


class InviteIn(BaseModel):
    role: Role
    name: str | None = None


class InviteOut(BaseModel):
    id: str
    role: str
    invitee_name: str | None = None
    token: str
    url: str
    status: str
    created_at: datetime


class InviteListItem(BaseModel):
    id: str
    role: str
    invitee_name: str | None = None
    token: str
    status: str
    created_at: datetime
