import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Intervalo = Literal[1, 3, 6, 12]


class PlanIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str | None = Field(None, max_length=500)
    precio: float = Field(gt=0, le=1_000_000)
    intervalo_meses: Intervalo = 1
    activo: bool = True


class PlanPatch(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=80)
    descripcion: str | None = Field(None, max_length=500)
    precio: float | None = Field(None, gt=0, le=1_000_000)
    intervalo_meses: Intervalo | None = None
    activo: bool | None = None


class CuponIn(BaseModel):
    codigo: str = Field(pattern=r"^[A-Za-z0-9_-]{3,30}$")
    descripcion: str | None = Field(None, max_length=300)
    tipo: Literal["porcentaje", "monto", "meses_gratis"]
    valor: float = Field(gt=0)
    num_cobros: int | None = Field(None, ge=1, le=60)
    vigente_hasta: date | None = None
    max_usos: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def _valor_segun_tipo(self):
        if self.tipo == "porcentaje" and self.valor >= 100:
            raise ValueError("El descuento debe ser menor a 100%. Para dar acceso gratis usa meses gratis.")
        if self.tipo == "meses_gratis":
            if self.valor != int(self.valor) or not 1 <= self.valor <= 36:
                raise ValueError("Los meses gratis deben ser un número entero entre 1 y 36.")
            self.num_cobros = None
        return self


class CuponPatch(BaseModel):
    descripcion: str | None = Field(None, max_length=300)
    vigente_hasta: date | None = None
    max_usos: int | None = Field(None, ge=1)
    activo: bool | None = None


class CodigoIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=40)
    plan_id: uuid.UUID | None = None


class SuscribirmeIn(BaseModel):
    plan_id: uuid.UUID
    codigo: str | None = Field(None, max_length=40)
