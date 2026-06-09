"""Seguimiento PM (nodo 6): estado de nudge de un compromiso, computado por fecha."""
from datetime import date


def nudge_estado(status: str, ref_date: date, fecha_compromiso: date | None, today: date) -> str:
    """ref_date = fecha del último avance, o la de creación si no hay avances."""
    if status == "completado":
        return "completado"
    if fecha_compromiso is not None and fecha_compromiso < today:
        return "vencido"
    dias = (today - ref_date).days
    if dias >= 21:
        return "sin_avance_rojo"
    if dias >= 14:
        return "sin_avance_amarillo"
    if dias >= 7:
        return "recordatorio"
    return "al_dia"
