"""Cobros: permisos del panel de admin, alta de cupones y planes, suscripción del cliente y
webhook de Stripe."""
import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user, get_db
from app.models.cobro import PlanSuscripcion, Suscripcion
from app.services.pagos import stripe_api as st

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
async def test_sin_stripe_no_se_puede_suscribir(monkeypatch):
    monkeypatch.setattr(st.settings, "STRIPE_SECRET_KEY", "")
    r = await _llamar("POST", "/pagos/suscribirme", json={"plan_id": "00000000-0000-0000-0000-000000000001"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_suscribirme_devuelve_la_liga_de_pago(monkeypatch):
    monkeypatch.setattr(st.settings, "STRIPE_SECRET_KEY", "sk_test_123")
    plan = PlanSuscripcion(nombre="Mensual", precio=Decimal("1000"), moneda="MXN", intervalo_meses=1, activo=True)
    crear = AsyncMock(return_value=Suscripcion(user_id="u1", email="cliente@empresa.com",
                                                liga_pago="https://checkout.stripe.test/pagar"))
    monkeypatch.setattr("app.api.v1.pagos.router.cobros.crear_suscripcion", crear)
    r_plan = MagicMock()
    r_plan.scalar_one_or_none.return_value = plan
    db = AsyncMock()
    db.execute = AsyncMock(return_value=r_plan)
    r = await _llamar("POST", "/pagos/suscribirme", db, json={"plan_id": str(plan.id)})
    assert r.status_code == 200, r.text
    assert r.json() == {"liga_pago": "https://checkout.stripe.test/pagar"}
    assert crear.await_args.kwargs["email"] == "cliente@empresa.com" and crear.await_args.kwargs["cupon"] is None


@pytest.mark.asyncio
async def test_portal_de_stripe(monkeypatch):
    monkeypatch.setattr(st.settings, "STRIPE_SECRET_KEY", "sk_test_123")
    sus = Suscripcion(user_id="u1", email="a@b.com", estado="activa", stripe_customer_id="cus_1")
    monkeypatch.setattr("app.api.v1.pagos.router.cobros.suscripcion_actual", AsyncMock(return_value=sus))
    portal = AsyncMock(return_value={"url": "https://billing.stripe.test/p"})
    monkeypatch.setattr(st, "crear_portal", portal)
    r = await _llamar("POST", "/pagos/portal")
    assert r.status_code == 200, r.text
    assert r.json() == {"url": "https://billing.stripe.test/p"}
    assert portal.await_args.args[0] == "cus_1" and portal.await_args.args[1].endswith("/dashboard/suscripcion")


@pytest.mark.asyncio
async def test_cancelar_no_corta_el_periodo_pagado(monkeypatch):
    monkeypatch.setattr(st.settings, "STRIPE_SECRET_KEY", "sk_test_123")
    sus = Suscripcion(user_id="u1", email="a@b.com", estado="activa", stripe_subscription_id="sub_1",
                      monto=Decimal("1000"), monto_regular=Decimal("1000"), moneda="MXN", intervalo_meses=1)
    monkeypatch.setattr("app.api.v1.pagos.router.cobros.suscripcion_actual", AsyncMock(return_value=sus))
    cancelar = AsyncMock(return_value={"status": "active", "cancel_at_period_end": True, "current_period_end": 1796212800})
    monkeypatch.setattr(st, "cancelar_al_final", cancelar)
    r = await _llamar("POST", "/pagos/cancelar")
    assert r.status_code == 200, r.text
    cancelar.assert_awaited_once_with("sub_1")
    out = r.json()["suscripcion"]
    assert out["estado"] == "activa" and out["vence"].startswith("2026-12-02") and out["proximo_cobro"] is None


@pytest.mark.asyncio
async def test_cupon_invalido_se_explica_al_cliente():
    r_vacio = MagicMock()
    r_vacio.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=r_vacio)
    r = await _llamar("POST", "/pagos/cupon", db, json={"codigo": "NOEXISTE"})
    assert r.status_code == 400
    assert "no existe" in r.json()["detail"]


def _evento(tipo: str, obj: dict) -> bytes:
    return json.dumps({"id": "evt_1", "type": tipo, "data": {"object": obj}}).encode()


def _firma(cuerpo: bytes, secreto: str = "whsec_x") -> str:
    t = int(time.time())
    return f"t={t},v1={hmac.new(secreto.encode(), f'{t}.'.encode() + cuerpo, hashlib.sha256).hexdigest()}"


@pytest.fixture
def _stripe(monkeypatch):
    monkeypatch.setattr(st.settings, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(st.settings, "STRIPE_WEBHOOK_SECRET", "whsec_x")


@pytest.mark.asyncio
async def test_webhook_con_firma_falsa(_stripe):
    cuerpo = _evento("invoice.paid", {"id": "in_1"})
    r = await _llamar("POST", "/pagos/webhook", email=None, content=cuerpo,
                      headers={"stripe-signature": _firma(cuerpo, "otro")})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_firmado_sincroniza_la_suscripcion(_stripe, monkeypatch):
    sincronizar = AsyncMock()
    monkeypatch.setattr("app.api.v1.pagos.router.cobros.sincronizar_suscripcion", sincronizar)
    sus = Suscripcion(user_id="u1", email="a@b.com", estado="pendiente", stripe_checkout_id="cs_1")
    r_sus = MagicMock()
    r_sus.scalar_one_or_none.return_value = sus
    db = AsyncMock()
    db.execute = AsyncMock(return_value=r_sus)
    cuerpo = _evento("checkout.session.completed", {"id": "cs_1", "client_reference_id": str(sus.id)})
    r = await _llamar("POST", "/pagos/webhook", db, email=None, content=cuerpo,
                      headers={"stripe-signature": _firma(cuerpo)})
    assert r.status_code == 200, r.text
    sincronizar.assert_awaited_once()
    assert sincronizar.await_args.args[1] is sus


@pytest.mark.asyncio
async def test_webhook_de_suscripcion_guarda_su_id(_stripe, monkeypatch):
    sincronizar = AsyncMock()
    monkeypatch.setattr("app.api.v1.pagos.router.cobros.sincronizar_suscripcion", sincronizar)
    sus = Suscripcion(user_id="u1", email="a@b.com", estado="pendiente", stripe_checkout_id="cs_1")
    r_sus = MagicMock()
    r_sus.scalar_one_or_none.return_value = sus
    db = AsyncMock()
    db.execute = AsyncMock(return_value=r_sus)
    cuerpo = _evento("customer.subscription.updated", {"id": "sub_1", "metadata": {"suscripcion_id": str(sus.id)}})
    r = await _llamar("POST", "/pagos/webhook", db, email=None, content=cuerpo,
                      headers={"stripe-signature": _firma(cuerpo)})
    assert r.status_code == 200, r.text
    assert sus.stripe_subscription_id == "sub_1"


@pytest.mark.asyncio
@pytest.mark.parametrize("tipo,estado", [("invoice.paid", "pagado"), ("invoice.payment_failed", "fallido")])
async def test_webhook_de_factura(_stripe, monkeypatch, tipo, estado):
    registrar = AsyncMock()
    monkeypatch.setattr("app.api.v1.pagos.router.cobros.registrar_pago", registrar)
    factura = {"id": "in_5", "subscription": "sub_1"}
    cuerpo = _evento(tipo, factura)
    r = await _llamar("POST", "/pagos/webhook", email=None, content=cuerpo,
                      headers={"stripe-signature": _firma(cuerpo)})
    assert r.status_code == 200
    assert registrar.await_args.args[1] == factura and registrar.await_args.args[2] == estado


@pytest.mark.asyncio
async def test_webhook_sin_secreto_vuelve_a_pedir_el_evento(monkeypatch):
    """Sin secreto no se confía en el cuerpo: el evento se pide a Stripe por su id."""
    monkeypatch.setattr(st.settings, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(st.settings, "STRIPE_WEBHOOK_SECRET", "")
    real = {"id": "evt_1", "type": "invoice.paid", "data": {"object": {"id": "in_real", "subscription": "sub_1"}}}
    obtener = AsyncMock(return_value=real)
    monkeypatch.setattr(st, "obtener_evento", obtener)
    registrar = AsyncMock()
    monkeypatch.setattr("app.api.v1.pagos.router.cobros.registrar_pago", registrar)
    r = await _llamar("POST", "/pagos/webhook", email=None,
                      content=_evento("invoice.paid", {"id": "in_falso", "subscription": "sub_1"}))
    assert r.status_code == 200
    obtener.assert_awaited_once_with("evt_1")
    assert registrar.await_args.args[1]["id"] == "in_real"
