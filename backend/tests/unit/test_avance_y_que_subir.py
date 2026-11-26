"""«¿Qué subo?» y «Avance contado a Todd» (pedido del dueño de Gobernia, 25 nov 2026): alguien sin
experiencia no sabe qué documento subir, y si no tiene ninguno, le cuenta a Todd qué hicieron."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import avance_todd
from app.services.ai import task_explainer as te
from app.services.pdf.avance_pdf import build_avance_pdf


def test_pdf_del_avance():
    pdf = build_avance_pdf("Caja & flujo <proyectado>", "Laura", datetime(2026, 11, 25, tzinfo=timezone.utc),
                           {"que_se_hizo": "Revisamos saldos con el banco", "resultado": "Saldo de $2.2 M"})
    assert pdf.startswith(b"%PDF") and len(pdf) > 800  # el «&» y «<…>» no rompen el PDF


@pytest.mark.asyncio
async def test_registrar_avance_lo_deja_como_evidencia(monkeypatch):
    subidos, agregados = [], []

    async def fake_upload(contenido, key):
        subidos.append(key)
    monkeypatch.setattr(avance_todd, "upload_to_storage", fake_upload)
    monkeypatch.setattr("app.services.evidencia_revision.flag_modified", lambda *a: None)
    task = SimpleNamespace(id=uuid.uuid4(), title="Caja y flujo", status="pendiente", validacion=None)
    db = SimpleNamespace(add=agregados.append)
    revision_id, archivo = await avance_todd.registrar_avance(
        db, task, avance_todd.datos_del_avance({"que_se_hizo": "x", "resultado": "y", "otro": "z"}), "Laura")
    assert archivo.startswith("Avance contado a Todd - ") and archivo.endswith(".pdf")
    assert len(subidos) == 1 and agregados[0].filename == archivo
    assert agregados[0].content_type == "application/pdf"
    assert task.status == "en_progreso" and task.validacion["estado"] == "revisando"
    assert task.validacion["revision_id"] == revision_id


def test_todd_detecta_cuando_guarda_un_avance():
    from app.services.ai import todd_secretario as ts
    uso = SimpleNamespace(type="tool_use", name="registrar_avance",
                          input={"task_id": "t1", "que_se_hizo": "x", "resultado": "y"})
    r = ts._parse_response(SimpleNamespace(content=[uso]))
    assert r["accion"] == {"tipo": "registrar_avance", "task_id": "t1", "que_se_hizo": "x", "resultado": "y"}
    assert r["reply"] == ""  # la confirmación la agrega el router
    assert ts.REGISTRAR_AVANCE_TOOL in ts._herramientas(None, None)


@pytest.mark.asyncio
async def test_guardar_avance_del_dueno_y_tarea_ajena(monkeypatch):
    from fastapi import HTTPException
    from app.api.v1.todd_secretario import router as tr
    tarea = SimpleNamespace(id=uuid.uuid4(), title="Caja y flujo")
    lanzadas = []

    async def propia(task_id, user_id, db):
        if task_id != tarea.id:
            raise HTTPException(status_code=404)
        return tarea

    async def fake_registrar(db, task, datos, quien):
        return "rev1", "Avance contado a Todd - 25 de noviembre de 2026.pdf"

    async def fake_revisar(task_id, user_id, revision_id, subido_por=None):
        lanzadas.append((task_id, revision_id))

    class Db:
        async def commit(self):
            pass
    monkeypatch.setattr(tr, "_get_user_task_or_404", propia)
    monkeypatch.setattr(avance_todd, "registrar_avance", fake_registrar)
    monkeypatch.setattr("app.services.evidencia_revision.revisar_evidencia_tarea", fake_revisar)

    out, texto = await tr._guardar_avance({"tipo": "registrar_avance", "task_id": str(tarea.id)}, "u1", Db())
    assert out == {"tipo": "registrar_avance", "task_id": str(tarea.id), "tarea": "Caja y flujo"}
    assert "«Avance contado a Todd»" in texto
    import asyncio
    await asyncio.sleep(0)
    assert lanzadas == [(tarea.id, "rev1")]
    assert await tr._guardar_avance({"task_id": str(uuid.uuid4())}, "u1", Db()) == (None, None)
    assert await tr._guardar_avance({"task_id": "no-es-id"}, "u1", Db()) == (None, None)


@pytest.mark.asyncio
async def test_que_subir_se_genera_una_vez_y_se_guarda(monkeypatch):
    from app.api.v1.action_plans import router as ap
    llamadas = []

    def fake_generar(title, desc, objetivo, empresa, required_doc):
        llamadas.append(required_doc)
        return {"pide": required_doc, "alternativas": ["Estados de cuenta"], "sin_documento": "Cuéntale…"}
    monkeypatch.setattr(ap, "generate_que_subir", fake_generar)
    monkeypatch.setattr(ap, "flag_modified", lambda *a: None)

    async def objetivo_empresa():
        return "Liquidez", "Acme"

    class Db:
        async def commit(self):
            pass
    task = SimpleNamespace(title="Caja", description=None, required_doc="Saldos bancarios",
                           explicacion={"que_es": "Qué es", "como": []})
    primero = await ap.que_subir_guardado(task, Db(), objetivo_empresa)
    segundo = await ap.que_subir_guardado(task, Db(), objetivo_empresa)
    assert primero == segundo and llamadas == ["Saldos bancarios"]  # la segunda vez sale guardado
    assert task.explicacion["que_es"] == "Qué es"  # la explicación de la tarea se conserva


@pytest.mark.asyncio
async def test_que_subir_no_guarda_si_la_ia_fallo(monkeypatch):
    from app.api.v1.action_plans import router as ap
    monkeypatch.setattr(ap, "generate_que_subir", lambda *a: te.parse_que_subir({}, "Saldos"))

    async def objetivo_empresa():
        return "", ""
    task = SimpleNamespace(title="Caja", description=None, required_doc="Saldos", explicacion=None)
    r = await ap.que_subir_guardado(task, None, objetivo_empresa)
    assert r["pide"] == "Saldos" and r["alternativas"] == [] and task.explicacion is None


def test_explicacion_visible_ignora_el_que_subir_solo():
    assert te.explicacion_visible({"evidencia": {"pide": "x"}}) is None
    assert te.explicacion_visible({"que_es": "Algo", "evidencia": {}})["que_es"] == "Algo"
    assert te.explicacion_visible(None) is None


def test_todd_del_responsable_puede_guardar_un_avance(monkeypatch):
    from app.services.ai import todd_responsable as tr
    uso = SimpleNamespace(type="tool_use", name="registrar_avance",
                          input={"task_id": "t1", "que_se_hizo": "x", "resultado": "y"})
    monkeypatch.setattr(tr.settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(tr.anthropic, "Anthropic", lambda **k: None)
    llamadas = []
    monkeypatch.setattr(tr, "pedir_texto", lambda *a, **k: llamadas.append(k) or SimpleNamespace(content=[uso]))
    r = tr.run_todd_responsable([{"role": "user", "content": "no tengo documento"}], "Laura", "Acme",
                                [{"task_id": "t1", "title": "Caja"}])
    assert r == {"reply": "", "avance": {"task_id": "t1", "que_se_hizo": "x", "resultado": "y"}}
    assert llamadas[0]["tools"] == [tr.REGISTRAR_AVANCE_TOOL]
    assert "[id: t1] Caja" in llamadas[0]["system"][0]["text"]
