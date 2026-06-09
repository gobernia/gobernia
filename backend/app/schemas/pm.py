from pydantic import BaseModel


class AvanceItem(BaseModel):
    fecha: str
    pct: int
    nota: str | None = None
    evidencia_url: str | None = None


class CompromisoOut(BaseModel):
    id: str
    descripcion: str
    responsable_email: str | None
    responsable_nombre: str | None
    fecha_compromiso: str | None
    status: str
    nudge: str
    token: str
    avances: list[AvanceItem]


class CompromisoPublicOut(BaseModel):
    descripcion: str
    fecha_compromiso: str | None
    status: str
    avances: list[AvanceItem]


class AvanceIn(BaseModel):
    pct: int
    nota: str | None = None
    evidencia_url: str | None = None


class ResponsablePatch(BaseModel):
    responsable_email: str | None = None
    responsable_nombre: str | None = None
    fecha_compromiso: str | None = None
