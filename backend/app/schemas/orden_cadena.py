"""Orden del día — cadena: documentos solicitados por cada prioridad aprobada.

Para cada prioridad (pilar) aprobada del Plan anual, la lista de documentos
(`required_doc` de sus tareas) que la sustentan, deduplicados.
"""
from pydantic import BaseModel


class DocSolicitado(BaseModel):
    doc: str
    n_tareas: int


class PuntoCadena(BaseModel):
    indice: int
    nombre: str
    objetivo: str
    kpis: list[dict]
    estrategias: list[str]
    documentos_solicitados: list[DocSolicitado]
    n_tareas: int


class OrdenCadenaOut(BaseModel):
    aprobado: bool
    anio: int
    puntos: list[PuntoCadena]
