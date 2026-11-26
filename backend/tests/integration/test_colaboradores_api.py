import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db
from app.models.action_plan import ActionTask
from app.models.colaborador import Colaborador
from app.models.onboarding_session import OnboardingSession

MOCK_USER_ID = "user_test_colab"


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_crear_link_nuevo_colaborador():
    # No existe → se crea uno nuevo con token.
    r_existente = MagicMock(); r_existente.scalar_one_or_none.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r_existente])
    db.add = MagicMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/v1/colaboradores/link",
                                  json={"email": "ana@empresa.com", "nombre": "Ana"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["token"]  # token no vacío
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_escritorio_publico_por_token():
    col = Colaborador(user_id=MOCK_USER_ID, email="Ana@Empresa.com", nombre="Ana", token="tok-abc")
    task = ActionTask(
        id=uuid.uuid4(), title="Definir cliente ideal", description="Perfilar",
        status="pendiente", due_date=date(2026, 9, 1), explicacion=None,
        validacion={"estado": "parcial", "motivo": "m", "falta": "La lista de clientes.", "revision_id": "x"},
    )
    r_col = MagicMock(); r_col.scalar_one_or_none.return_value = col
    onb = OnboardingSession(user_id=MOCK_USER_ID, memory_buffer={"company": {"name": "Acme"}})
    r_onb = MagicMock(); r_onb.scalars.return_value.first.return_value = onb
    r_tareas = MagicMock(); r_tareas.all.return_value = [(task, "Crecer ventas")]
    r_conteo = MagicMock(); r_conteo.all.return_value = [(task.id, 2)]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r_col, r_onb, r_tareas, r_conteo])
    app.dependency_overrides[get_db] = _db_override(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/v1/t/tok-abc")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["nombre"] == "Ana"
    assert body["empresa"] == "Acme"
    assert len(body["tareas"]) == 1
    t = body["tareas"][0]
    assert t["title"] == "Definir cliente ideal"
    assert t["objetivo"] == "Crecer ventas"
    assert t["tiene_explicacion"] is False
    # Ve cuántos documentos tiene su tarea y lo que dijo el Auditor (sin datos internos).
    assert t["evidencias"] == 2
    assert t["validacion"] == {"estado": "parcial", "motivo": "m", "falta": "La lista de clientes."}


@pytest.mark.asyncio
async def test_escritorio_token_inexistente_404():
    r_col = MagicMock(); r_col.scalar_one_or_none.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r_col])
    app.dependency_overrides[get_db] = _db_override(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/v1/t/nope")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404



def _db_subida(col, fila):
    r_col = MagicMock(); r_col.scalar_one_or_none.return_value = col
    r_tarea = MagicMock(); r_tarea.first.return_value = fila
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r_col, r_tarea])
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_responsable_sube_evidencia_de_su_tarea(monkeypatch):
    """El responsable sube desde su enlace; el Auditor la revisa y el aviso dice quién la subió."""
    from app.api.v1.colaboradores import router as colab
    col = Colaborador(user_id=MOCK_USER_ID, email="laura@empresa.com", nombre="Laura", token="tok-l")
    task = ActionTask(id=uuid.uuid4(), title="Caja y flujo", status="pendiente", validacion=None)
    db = _db_subida(col, (task, "Liquidez"))
    revisiones = []

    async def fake_revisar(task_id, user_id, revision_id, subido_por=None):
        revisiones.append((task_id, user_id, subido_por))
    monkeypatch.setattr(colab, "revisar_evidencia_tarea", fake_revisar)
    monkeypatch.setattr(colab, "flag_modified", lambda *a: None, raising=False)
    monkeypatch.setattr("app.services.evidencia_revision.flag_modified", lambda *a: None)
    app.dependency_overrides[get_db] = _db_override(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(f"/api/v1/t/tok-l/tareas/{task.id}/evidencia",
                                  files={"file": ("saldos.pdf", b"%PDF-1.4 saldos", "application/pdf")})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200 and r.json()["filename"] == "saldos.pdf"
    db.add.assert_called_once()
    assert task.status == "en_progreso" and task.validacion["estado"] == "revisando"
    assert revisiones == [(task.id, MOCK_USER_ID, "Laura")]  # se revisa como del dueño, con su nombre


@pytest.mark.asyncio
async def test_responsable_no_puede_subir_a_una_tarea_ajena():
    col = Colaborador(user_id=MOCK_USER_ID, email="laura@empresa.com", nombre="Laura", token="tok-l")
    db = _db_subida(col, None)  # la tarea no es suya
    app.dependency_overrides[get_db] = _db_override(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(f"/api/v1/t/tok-l/tareas/{uuid.uuid4()}/evidencia",
                                  files={"file": ("x.pdf", b"%PDF", "application/pdf")})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_responsable_no_puede_subir_tipos_no_permitidos():
    col = Colaborador(user_id=MOCK_USER_ID, email="laura@empresa.com", nombre="Laura", token="tok-l")
    task = ActionTask(id=uuid.uuid4(), title="Caja y flujo", status="pendiente", validacion=None)
    db = _db_subida(col, (task, "Liquidez"))
    app.dependency_overrides[get_db] = _db_override(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(f"/api/v1/t/tok-l/tareas/{task.id}/evidencia",
                                  files={"file": ("virus.exe", b"MZ", "application/octet-stream")})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400
    db.add.assert_not_called()
