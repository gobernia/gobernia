"""Cobros: permisos del panel de admin, alta de cupones y planes, suscripción del cliente y
webhook de Mercado Pago."""
import hashlib
import hmac
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user, get_db
from app.models.cobro import PlanSuscripcion, Suscripcion
from app.services.pagos import mercadopago as mp

ADMIN = "jefe@gobernia.ai"


def _como(email: str):
    async def override():
        return {"sub": "u1", "email": email}
    return override


async def _llamar(metodo: str, path: str, db=None, email: str | None = "cliente@empresa.com", **kw):
    if email:
        app.dependency_overrides[get_current_user] = _como(email)
    db = db or AsyncMock()

    async def _db():
        yield db
    app.dependency_overrides[get_db] = _db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.request(metodo, f"/api/v1{path}", **kw)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _admin(monkeypatch):
    monkeypatch.setattr("app.api.v1.admin.router.settings.SUPERADMIN_EMAILS", [ADMIN])


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo,path,body", [
    ("GET", "/admin/cobros", None),
    ("POST", "/admin/planes", {"nombre": "Mensual", "precio": 1000}),
    ("PATCH", "/admin/planes/00000000-0000-0000-0000-000000000001", {"activo": False}),
    ("POST", "/admin/cupones", {"codigo": "HOLA20", "tipo": "porcentaje", "valor": 20}),
    ("PATCH", "/admin/cupones/00000000-0000-0000-0000-000000000001", {"activo": False}),
])
async def test_un_cliente_no_administra_cobros(metodo, path, body):
    r = await _llamar(metodo, path, json=body)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_crear_cupon_normaliza_el_codigo():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    db.add = MagicMock()
    r = await _llamar("POST", "/admin/cupones", db, ADMIN, json={
        "codigo": "aliado-3", "tipo": "meses_gratis", "valor": 3, "max_usos": 10, "vigente_hasta": "2026-12-31"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["codigo"] == "ALIADO-3" and body["resumen"] == "3 meses gratis"
    assert body["max_usos"] == 10 and body["vigente_hasta"] == "2026-12-31"


@pytest.mark.asyncio
async def test_no_se_repite_un_codigo_de_cupon():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value="ya-existe")
    r = await _llamar("POST", "/admin/cupones", db, ADMIN, json={"codigo": "HOLA20", "tipo": "porcentaje", "valor": 20})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_crear_plan():
    db = AsyncMock()
    db.add = MagicMock()
    r = await _llamar("POST", "/admin/planes", db, ADMIN, json={"nombre": "Anual", "precio": 9999.5, "intervalo_meses": 12})
    assert r.status_code == 200, r.text
    assert r.json()["precio"] == 9999.5 and r.json()["intervalo_meses"] == 12
    plan = db.add.call_args.args[0]
    assert isinstance(plan, PlanSuscripcion) and plan.precio == Decimal("9999.50")


@pytest.mark.asyncio
async def test_plan_con_intervalo_invalido():
    r = await _llamar("POST", "/admin/planes", None, ADMIN, json={"nombre": "Raro", "precio": 100, "intervalo_meses": 2})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_sin_mercado_pago_no_se_puede_suscribir(monkeypatch):
    monkeypatch.setattr(mp.settings, "MERCADOPAGO_ACCESS_TOKEN", "")
    r = await _llamar("POST", "/pagos/suscribirme", json={"plan_id": "00000000-0000-0000-0000-000000000001"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_suscribirme_devuelve_la_liga_de_pago(monkeypatch):
    monkeypatch.setattr(mp.settings, "MERCADOPAGO_ACCESS_TOKEN", "TEST-123")
    plan = PlanSuscripcion(nombre="Mensual", precio=Decimal("1000"), moneda="MXN", intervalo_meses=1, activo=True)
    crear = AsyncMock(return_value=Suscripcion(user_id="u1", email="cliente@empresa.com",
                                                mp_init_point="https://mp.test/pagar"))
    monkeypatch.setattr("app.api.v1.pagos.router.cobros.crear_suscripcion", crear)
    r_plan = MagicMock()
    r_plan.scalar_one_or_none.return_value = plan
    db = AsyncMock()
    db.execute = AsyncMock(return_value=r_plan)
    r = await _llamar("POST", "/pagos/suscribirme", db, json={"plan_id": str(plan.id)})
    assert r.status_code == 200, r.text
    assert r.json() == {"liga_pago": "https://mp.test/pagar"}
    assert crear.await_args.kwargs["email"] == "cliente@empresa.com" and crear.await_args.kwargs["cupon"] is None


@pytest.mark.asyncio
async def test_cupon_invalido_se_explica_al_cliente():
    r_vacio = MagicMock()
    r_vacio.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=r_vacio)
    r = await _llamar("POST", "/pagos/cupon", db, json={"codigo": "NOEXISTE"})
    assert r.status_code == 400
    assert "no existe" in r.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_con_firma_falsa(monkeypatch):
    monkeypatch.setattr(mp.settings, "MERCADOPAGO_WEBHOOK_SECRET", "secreto")
    r = await _llamar("POST", "/pagos/webhook?data.id=pre1&type=subscription_preapproval", email=None,
                      json={"type": "subscription_preapproval", "data": {"id": "pre1"}},
                      headers={"x-signature": "ts=1,v1=falsa", "x-request-id": "req"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_firmado_sincroniza_la_suscripcion(monkeypatch):
    monkeypatch.setattr(mp.settings, "MERCADOPAGO_WEBHOOK_SECRET", "secreto")
    monkeypatch.setattr(mp.settings, "MERCADOPAGO_ACCESS_TOKEN", "TEST-123")
    sincronizar = AsyncMock()
    monkeypatch.setattr("app.api.v1.pagos.router.cobros.sincronizar_suscripcion", sincronizar)
    sus = Suscripcion(user_id="u1", email="a@b.com", estado="pendiente", mp_preapproval_id="pre1")
    r_sus = MagicMock()
    r_sus.scalar_one_or_none.return_value = sus
    db = AsyncMock()
    db.execute = AsyncMock(return_value=r_sus)
    v1 = hmac.new(b"secreto", b"id:pre1;request-id:req-1;ts:99;", hashlib.sha256).hexdigest()
    r = await _llamar("POST", "/pagos/webhook?data.id=pre1&type=subscription_preapproval", db, email=None,
                      json={"type": "subscription_preapproval", "data": {"id": "pre1"}},
                      headers={"x-signature": f"ts=99,v1={v1}", "x-request-id": "req-1"})
    assert r.status_code == 200, r.text
    sincronizar.assert_awaited_once()
    assert sincronizar.await_args.args[1] is sus


@pytest.mark.asyncio
async def test_webhook_de_cobro(monkeypatch):
    monkeypatch.setattr(mp.settings, "MERCADOPAGO_WEBHOOK_SECRET", "")
    monkeypatch.setattr(mp.settings, "MERCADOPAGO_ACCESS_TOKEN", "TEST-123")
    cobro = {"id": 5, "preapproval_id": "pre1"}
    monkeypatch.setattr(mp, "obtener_cobro", AsyncMock(return_value=cobro))
    registrar = AsyncMock()
    monkeypatch.setattr("app.api.v1.pagos.router.cobros.registrar_cobro", registrar)
    r = await _llamar("POST", "/pagos/webhook?data.id=5&type=subscription_authorized_payment", email=None,
                      json={"type": "subscription_authorized_payment", "data": {"id": "5"}})
    assert r.status_code == 200
    assert registrar.await_args.args[1] == cobro
