from datetime import date, timedelta

from app.services.governance.pm import nudge_estado
from app.models.compromiso import Compromiso

TODAY = date(2026, 6, 15)


def test_completado():
    assert nudge_estado("completado", TODAY, TODAY, TODAY) == "completado"


def test_vencido():
    assert nudge_estado("abierto", TODAY, TODAY - timedelta(days=1), TODAY) == "vencido"


def test_vencido_gana_sobre_actividad():
    assert nudge_estado("en_progreso", TODAY, TODAY - timedelta(days=2), TODAY) == "vencido"


def test_al_dia():
    assert nudge_estado("abierto", TODAY - timedelta(days=3), None, TODAY) == "al_dia"


def test_recordatorio_7():
    assert nudge_estado("abierto", TODAY - timedelta(days=7), None, TODAY) == "recordatorio"


def test_amarillo_14():
    assert nudge_estado("en_progreso", TODAY - timedelta(days=14), None, TODAY) == "sin_avance_amarillo"


def test_rojo_21():
    assert nudge_estado("abierto", TODAY - timedelta(days=21), None, TODAY) == "sin_avance_rojo"


def test_modelo_compromiso():
    c = Compromiso(user_id="u1", descripcion="Hacer X", status="abierto", token="tok123", avances=[])
    assert c.descripcion == "Hacer X"
    assert c.token == "tok123"
    assert c.id is not None  # default uuid4
