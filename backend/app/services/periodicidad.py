"""Periodicidad de las tareas del plan: cada cuánto se reparten y revisan los puntos.

El plan siempre abarca 36 meses (MonthlyPlan por mes). La periodicidad solo agrupa esos
meses en bloques: mensual (1 mes), trimestral (3) o semestral (6). Cada bloque tiene su
propio orden del día de 4-8 puntos, con fechas límite repartidas dentro del bloque.
"""
import unicodedata

MESES_POR_PERIODO = {"mensual": 1, "trimestral": 3, "semestral": 6}
PERIODICIDAD_DEFAULT = "mensual"

_MESES_CORTOS = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def norm_periodicidad(v) -> str:
    """Normaliza lo que venga (del onboarding de Todd, del frontend) a mensual|trimestral|semestral."""
    s = unicodedata.normalize("NFD", str(v or "")).encode("ascii", "ignore").decode().lower()
    if "semest" in s or "6 mes" in s or "seis" in s:
        return "semestral"
    if "trimest" in s or "3 mes" in s or "tres" in s:
        return "trimestral"
    return "mensual"


def meses_por_periodo(periodicidad: str | None) -> int:
    return MESES_POR_PERIODO.get(norm_periodicidad(periodicidad), 1)


def periodo_de_mes(month_index: int, periodicidad: str | None) -> int:
    """Número de periodo (1-based) al que pertenece un mes global (1-based)."""
    return (month_index - 1) // meses_por_periodo(periodicidad) + 1


def etiqueta_periodo(meses: list[tuple[int, int]], periodicidad: str | None, numero: int) -> str:
    """Etiqueta legible de un periodo. `meses`: [(año, mes), ...] en orden.
    mensual → «Marzo 2026» lo arma quien llama; aquí: «Trimestre 2 · Ene–Mar 2027»."""
    p = norm_periodicidad(periodicidad)
    (a1, m1), (a2, m2) = meses[0], meses[-1]
    if (a1, m1) == (a2, m2):
        rango = f"{_MESES_CORTOS[m1]} {a1}"
    elif a1 == a2:
        rango = f"{_MESES_CORTOS[m1]}–{_MESES_CORTOS[m2]} {a2}"
    else:
        rango = f"{_MESES_CORTOS[m1]} {a1}–{_MESES_CORTOS[m2]} {a2}"
    nombre = "Trimestre" if p == "trimestral" else "Semestre"
    return f"{nombre} {numero} · {rango}"


def periodicidad_de_onboarding(memory_buffer: dict | None) -> str | None:
    """La elección hecha con Todd en el onboarding, si existe."""
    gov = ((memory_buffer or {}).get("governance") or {})
    v = gov.get("periodicidad_tareas")
    return norm_periodicidad(v) if v else None
