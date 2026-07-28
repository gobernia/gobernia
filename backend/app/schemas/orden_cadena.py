"""Orden del día — cadena: documentos solicitados por cada prioridad aprobada.

Para cada prioridad (pilar) aprobada del Plan anual, la lista de documentos
(`required_doc` de sus tareas) que la sustentan, deduplicados.
"""
from pydantic import BaseModel


class DocSolicitado(BaseModel):
    doc: str
    n_tareas: int


# ── Análisis del punto (formato fijo del PDF, calculado de forma determinista) ──


class QueSeEsperaba(BaseModel):
    meta: str
    tareas_planeadas: int


class QueOcurrio(BaseModel):
    hechas: int
    en_proceso: int
    pendientes: int
    kpis: list[dict]


class Evidencia(BaseModel):
    documentos_subidos: int


class Desviacion(BaseModel):
    tareas_vencidas: int
    kpis_sin_dato: int


class AnalisisPunto(BaseModel):
    que_se_esperaba: QueSeEsperaba
    que_ocurrio: QueOcurrio
    evidencia: Evidencia
    desviacion: Desviacion
    explicacion: str | None
    decision_sugerida: str


class PuntoCadena(BaseModel):
    indice: int
    nombre: str
    objetivo: str
    kpis: list[dict]
    estrategias: list[str]
    documentos_solicitados: list[DocSolicitado]
    n_tareas: int
    analisis: AnalisisPunto


class OrdenCadenaOut(BaseModel):
    aprobado: bool
    anio: int
    puntos: list[PuntoCadena]
