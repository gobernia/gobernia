"""Revisión inmediata de la evidencia: el Auditor lee el documento al subirlo."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import evidencia_revision as er


def test_validacion_visible_revisando_reciente_se_muestra():
    v = {"estado": "revisando", "desde": datetime.now(timezone.utc).isoformat(), "revision_id": "x"}
    assert er.validacion_visible(v)["estado"] == "revisando"


def test_validacion_visible_revisando_colgada_pasa_a_sin_revisar():
    viejo = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    assert er.validacion_visible({"estado": "revisando", "desde": viejo})["estado"] == "sin_revisar"


def test_validacion_visible_oculta_rastro_interno():
    out = er.validacion_visible({"estado": "validada", "motivo": "ok", "revision_id": "x", "origen": "al_subir"})
    assert out == {"estado": "validada", "motivo": "ok", "origen": "al_subir"}  # sin revision_id


def test_validacion_visible_lleva_lo_que_falta_y_las_alternativas():
    v = {"estado": "parcial", "motivo": "m", "cubre": "Saldos al 23 nov.", "falta": "La proyección.",
         "alternativas": ["Tabla de cobros y pagos esperados"], "revision_id": "x"}
    assert er.validacion_visible(v) == {k: v[k] for k in ("estado", "motivo", "cubre", "falta", "alternativas")}


def test_marcar_revisando_asigna_id_nuevo():
    task = SimpleNamespace(validacion=None)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(er, "flag_modified", lambda *a: None)
        rid = er.marcar_revisando(task)
    assert task.validacion["estado"] == "revisando" and task.validacion["revision_id"] == rid


class _FakeResult:
    def __init__(self, items, uno=None):
        self._items = items
        self._uno = uno

    def scalars(self):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None

    def scalar_one_or_none(self):
        return self._uno


class _FakeSession:
    def __init__(self, task, anchor=None):
        self.task = task
        self.anchor = anchor
        self.committed = False
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, model, _id):
        return self.task

    async def execute(self, stmt):
        # Sin evidencias ni onboarding; la consulta de un solo resultado es la sesión de Consejo
        # (el ancla del chat de Todd).
        return _FakeResult([], uno=self.anchor)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("rid_actual, escribe", [("r1", True), ("otra", False)])
async def test_revisar_escribe_solo_si_es_la_revision_vigente(monkeypatch, rid_actual, escribe):
    tid = uuid.uuid4()
    task = SimpleNamespace(id=tid, title="Presentar flujo", status="en_progreso", required_doc=None,
                           description=None, validacion={"estado": "revisando", "revision_id": rid_actual})
    monkeypatch.setattr(er, "AsyncSessionLocal", lambda: _FakeSession(task))
    monkeypatch.setattr(er, "flag_modified", lambda *a: None)

    async def fake_validar(cands, mb):
        return {str(tid): {"estado": "validada", "motivo": "El flujo lo respalda."}}
    monkeypatch.setattr("app.api.v1.board_sessions.router._validar_evidencias_del_periodo", fake_validar)

    await er.revisar_evidencia_tarea(tid, "u1", "r1")
    if escribe:
        assert task.validacion["estado"] == "validada" and task.validacion["origen"] == "al_subir"
    else:
        assert task.validacion["estado"] == "revisando"


@pytest.mark.asyncio
async def test_revisar_si_falla_la_ia_queda_sin_revisar(monkeypatch):
    tid = uuid.uuid4()
    task = SimpleNamespace(id=tid, title="t", status="en_progreso", required_doc=None, description=None,
                           validacion={"estado": "revisando", "revision_id": "r1"})
    monkeypatch.setattr(er, "AsyncSessionLocal", lambda: _FakeSession(task))
    monkeypatch.setattr(er, "flag_modified", lambda *a: None)

    async def boom(cands, mb):
        raise RuntimeError("API caída")
    monkeypatch.setattr("app.api.v1.board_sessions.router._validar_evidencias_del_periodo", boom)

    await er.revisar_evidencia_tarea(tid, "u1", "r1")
    assert task.validacion["estado"] == "sin_revisar"


@pytest.mark.asyncio
async def test_al_terminar_todd_deja_en_su_chat_que_esta_que_falta_y_que_mas_sirve(monkeypatch):
    """Pedido del dueño: en vez de solo "falta sustento", Todd le dice al cliente qué hacer."""
    tid = uuid.uuid4()
    task = SimpleNamespace(id=tid, title="Caja y flujo proyectado", status="en_progreso",
                           required_doc="Saldos de bancos y proyección de flujo a 3 meses",
                           description="Presentar la posición de caja", validacion={"revision_id": "r1"})
    sesion = _FakeSession(task, anchor=uuid.uuid4())
    monkeypatch.setattr(er, "AsyncSessionLocal", lambda: sesion)
    monkeypatch.setattr(er, "flag_modified", lambda *a: None)
    candidatos = []

    async def fake_validar(cands, mb):
        candidatos.extend(cands)
        return {str(tid): {"estado": "parcial", "motivo": "Solo saldos.", "cubre": "Saldos al 23 nov.",
                           "falta": "La proyección de flujo.", "alternativas": ["Tabla de cobros y pagos"]}}
    monkeypatch.setattr("app.api.v1.board_sessions.router._validar_evidencias_del_periodo", fake_validar)

    await er.revisar_evidencia_tarea(tid, "u1", "r1")
    assert candidatos[0]["required_doc"] == "Saldos de bancos y proyección de flujo a 3 meses"
    assert task.validacion["estado"] == "parcial" and task.validacion["falta"] == "La proyección de flujo."
    [msg] = sesion.added
    assert msg.role == "assistant" and msg.agent == "todd_secretario"
    assert "Saldos al 23 nov." in msg.content and "La proyección de flujo." in msg.content
    assert "Tabla de cobros y pagos" in msg.content
    assert msg.message_metadata["revision"] == {"task_id": str(tid), "tarea": "Caja y flujo proyectado",
                                                "archivo": "tu documento", "estado": "parcial",
                                                "documento": "", "otro_documento": False}


def test_mensaje_de_todd_segun_el_veredicto():
    from app.services.evidencia_todd import mensaje_de_todd
    ok = mensaje_de_todd({"estado": "validada", "motivo": "El contrato firmado lo respalda."}, "Firmar", "c.pdf")
    assert "validado" in ok and "El contrato firmado" in ok and "Falta" not in ok
    falta = mensaje_de_todd({"estado": "insuficiente", "motivo": "Es solo una cotización."}, "ERP", "cot.pdf")
    assert "**Falta:** Es solo una cotización." in falta and "Ya está" not in falta
    roto = mensaje_de_todd({"estado": "sin_revisar", "motivo": ""}, "ERP", "viejo.xls")
    assert "no pude leerlo" in roto and "PDF" in roto


def test_mensaje_de_todd_si_subieron_otro_documento():
    """Pedido del dueño: si sube su CV por error, Todd le dice qué es y qué necesita."""
    from app.services.evidencia_todd import mensaje_de_todd
    m = mensaje_de_todd({"estado": "insuficiente", "motivo": "Es un CV.", "documento": "un currículum (CV)",
                         "otro_documento": True, "falta": "Saldos bancarios y proyección de flujo a 3 meses.",
                         "alternativas": ["Estados de cuenta de noviembre"]}, "Caja y flujo", "CV.pdf")
    assert "te equivocaste de documento" in m and "**un currículum (CV)**" in m
    assert "**Para esta tarea necesito:** Saldos bancarios y proyección de flujo a 3 meses." in m
    assert "Estados de cuenta de noviembre" in m
    del_tema = mensaje_de_todd({"estado": "parcial", "motivo": "m", "documento": "saldos al 23 nov",
                                "falta": "La proyección."}, "Caja y flujo", "s.xlsx")
    assert "(saldos al 23 nov)" in del_tema and "equivocaste" not in del_tema
