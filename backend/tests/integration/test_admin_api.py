"""Panel de super admin: solo SUPERADMIN_EMAILS puede verlo."""
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user, get_db


def _como(email: str):
    async def override():
        return {"sub": "u1", "email": email}
    return override


async def _db():
    yield AsyncMock()


async def _get(path: str, email: str):
    app.dependency_overrides[get_current_user] = _como(email)
    app.dependency_overrides[get_db] = _db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.get(f"/api/v1{path}")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_un_cliente_no_puede_ver_el_panel(monkeypatch):
    monkeypatch.setattr("app.api.v1.admin.router.settings.SUPERADMIN_EMAILS", ["jefe@gobernia.ai"])
    r = await _get("/admin/resumen", "cliente@empresa.com")
    assert r.status_code == 403
    assert (await _get("/admin/me", "cliente@empresa.com")).json() == {"es_admin": False}


@pytest.mark.asyncio
async def test_el_super_admin_ve_el_panel(monkeypatch):
    monkeypatch.setattr("app.api.v1.admin.router.settings.SUPERADMIN_EMAILS", ["Jefe@Gobernia.ai"])
    usuarios = [
        {"etapa": "sesionando", "registrado": None, "ultimo_acceso": None, "sesiones": 2, "plan_estado": "active"},
        {"etapa": "registrado", "registrado": None, "ultimo_acceso": None, "sesiones": 0, "plan_estado": None},
    ]
    monkeypatch.setattr("app.api.v1.admin.router._usuarios", AsyncMock(return_value=usuarios))
    r = await _get("/admin/resumen", "jefe@gobernia.ai")
    assert r.status_code == 200
    body = r.json()
    assert body["usuarios_total"] == 2 and body["sesiones_total"] == 2 and body["con_plan"] == 1
    embudo = {e["etapa"]: e["usuarios"] for e in body["embudo"]}
    assert embudo["registrado"] == 2 and embudo["sesionando"] == 1
    assert (await _get("/admin/me", "jefe@gobernia.ai")).json() == {"es_admin": True}
