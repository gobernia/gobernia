"""
Formatters del bloque de EJECUCIÓN que /analyse le pasa a la deliberación:
- `_format_avance_tareas`: totales + detalle del periodo actual + arrastradas.
- `_format_acuerdos_previos`: acuerdos abiertos de sesiones anteriores, con marca de vencido.
"""
from datetime import date
from types import SimpleNamespace

from app.api.v1.board_sessions.router import (
    _format_acuerdos_previos,
    _format_avance_tareas,
)


def _obj(oid):
    return SimpleNamespace(id=oid)


def _month(idx, period_month, objectives):
    return SimpleNamespace(month_index=idx, period_month=period_month,
                           period_year=2026, objectives=objectives)


def _task(title, status, owner=None):
    return SimpleNamespace(title=title, status=status, owner=owner)


def test_avance_totales_periodo_y_arrastradas():
    o1, o2, o3 = _obj("o1"), _obj("o2"), _obj("o3")
    months = [
        _month(1, 1, [o1]),   # Enero
        _month(2, 2, [o2]),   # Febrero
        _month(3, 3, [o3]),   # Marzo (actual)
    ]
    tasks_by_obj = {
        "o1": [_task("Enero hecha", "completada"),
               _task("Enero pendiente", "pendiente", owner="Finanzas")],
        "o2": [_task("Febrero en curso", "en_progreso")],
        "o3": [_task("Marzo propia", "pendiente", owner="Ventas")],
    }

    txt = _format_avance_tareas(months, tasks_by_obj, active_index=3)

    # Totales: 1 completada, 1 en proceso, 2 sin ejecutar, de 4.
    assert "1 completada(s), 1 en proceso, 2 sin ejecutar (de 4 tareas)" in txt
    # Periodo actual (Marzo 2026) con su tarea propia y responsable.
    assert "Tareas del periodo actual (Marzo 2026):" in txt
    assert "[sin ejecutar] Marzo propia (resp. Ventas)" in txt
    # Arrastradas: las incompletas de meses anteriores, con su origen. La completada NO se arrastra.
    assert "Tareas arrastradas de meses anteriores (incompletas):" in txt
    assert "[sin ejecutar] Enero pendiente (resp. Finanzas) — viene de Enero 2026" in txt
    assert "[en proceso] Febrero en curso — viene de Febrero 2026" in txt
    assert "Enero hecha" not in txt


def test_avance_sin_tareas_devuelve_none():
    months = [_month(1, 1, [_obj("o1")])]
    assert _format_avance_tareas(months, {"o1": []}, active_index=1) is None


def test_avance_mes_actual_sin_arrastre():
    months = [_month(1, 1, [_obj("o1")])]
    tasks_by_obj = {"o1": [_task("Sola", "pendiente")]}
    txt = _format_avance_tareas(months, tasks_by_obj, active_index=1)
    assert "Tareas del periodo actual (Enero 2026):" in txt
    assert "arrastradas" not in txt.lower()


def test_acuerdos_previos_marca_vencido():
    today = date(2026, 7, 1)
    rows = [
        SimpleNamespace(descripcion="Contratar auditor", responsable_nombre="Dirección General",
                        fecha_compromiso=date(2026, 5, 1), status="abierto"),
        SimpleNamespace(descripcion="Cerrar caja", responsable_nombre=None,
                        fecha_compromiso=date(2026, 9, 1), status="en_progreso"),
        SimpleNamespace(descripcion="Sin fecha", responsable_nombre="Finanzas",
                        fecha_compromiso=None, status="abierto"),
    ]
    txt = _format_acuerdos_previos(rows, today)

    assert "Contratar auditor · resp. Dirección General · fecha 2026-05-01 · estatus «abierto» — VENCIDO" in txt
    # No vencido (fecha futura) y sin responsable asignado.
    assert "Cerrar caja · resp. (sin responsable asignado) · fecha 2026-09-01 · estatus «en_progreso»" in txt
    assert "Cerrar caja" in txt and "Cerrar caja · resp. (sin responsable asignado) · fecha 2026-09-01 · estatus «en_progreso» — VENCIDO" not in txt
    # Sin fecha: no se marca vencido.
    assert "Sin fecha · resp. Finanzas · fecha (sin fecha) · estatus «abierto»" in txt


def test_acuerdos_previos_vacio_devuelve_none():
    assert _format_acuerdos_previos([], date(2026, 7, 1)) is None
