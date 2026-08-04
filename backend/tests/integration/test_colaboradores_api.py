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
    )
    r_col = MagicMock(); r_col.scalar_one_or_none.return_value = col
    onb = OnboardingSession(user_id=MOCK_USER_ID, memory_buffer={"company": {"name": "Acme"}})
    r_onb = MagicMock(); r_onb.scalars.return_value.first.return_value = onb
    r_tareas = MagicMock(); r_tareas.all.return_value = [(task, "Crecer ventas")]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r_col, r_onb, r_tareas])
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
