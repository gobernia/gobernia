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
    assert out == {"estado": "validada", "motivo": "ok"}


def test_marcar_revisando_asigna_id_nuevo():
    task = SimpleNamespace(validacion=None)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(er, "flag_modified", lambda *a: None)
        rid = er.marcar_revisando(task)
    assert task.validacion["estado"] == "revisando" and task.validacion["revision_id"] == rid


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class _FakeSession:
    def __init__(self, task):
        self.task = task
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, model, _id):
        return self.task

    async def execute(self, stmt):
        return _FakeResult([])

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
@pytest.mark.parametrize("rid_actual, escribe", [("r1", True), ("otra", False)])
async def test_revisar_escribe_solo_si_es_la_revision_vigente(monkeypatch, rid_actual, escribe):
    tid = uuid.uuid4()
    task = SimpleNamespace(id=tid, title="Presentar flujo", status="en_progreso",
                           validacion={"estado": "revisando", "revision_id": rid_actual})
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
    task = SimpleNamespace(id=tid, title="t", status="en_progreso",
                           validacion={"estado": "revisando", "revision_id": "r1"})
    monkeypatch.setattr(er, "AsyncSessionLocal", lambda: _FakeSession(task))
    monkeypatch.setattr(er, "flag_modified", lambda *a: None)

    async def boom(cands, mb):
        raise RuntimeError("API caída")
    monkeypatch.setattr("app.api.v1.board_sessions.router._validar_evidencias_del_periodo", boom)

    await er.revisar_evidencia_tarea(tid, "u1", "r1")
    assert task.validacion["estado"] == "sin_revisar"
