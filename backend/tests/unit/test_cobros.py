"""Reglas de cobro: cupones, precios, descuentos por tiempo limitado, Stripe y firma del webhook."""
import hashlib
import hmac
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.models.cobro import Cupon, Pago, PlanSuscripcion, Suscripcion
from app.schemas.pagos import CuponIn
from app.services.pagos import cobros
from app.services.pagos import stripe_api as st


def _cupon(**kw):
    base = dict(codigo="BIENVENIDA", tipo="porcentaje", valor=Decimal("20"), num_cobros=None,
                vigente_hasta=None, max_usos=None, activo=True)
    return Cupon(**{**base, **kw})


def _resultado(valor):
    r = MagicMock()
    r.scalar_one_or_none.return_value = valor
    r.scalars.return_value.all.return_value = valor if isinstance(valor, list) else []
    return r


def test_precio_con_cupon():
    assert cobros.precio_con_cupon(1000, _cupon(valor=Decimal("20"))) == Decimal("800.00")
    assert cobros.precio_con_cupon(1000, _cupon(tipo="monto", valor=Decimal("250"))) == Decimal("750.00")
    assert cobros.precio_con_cupon(100, _cupon(tipo="monto", valor=Decimal("500"))) == Decimal("0")
    assert cobros.precio_con_cupon(1000, _cupon(tipo="meses_gratis", valor=Decimal("3"))) == Decimal("1000.00")
    assert cobros.precio_con_cupon("999.99", None) == Decimal("999.99")


def test_describir_cupon():
    assert cobros.describir_cupon(_cupon()) == "20% de descuento en cada cobro"
    assert cobros.describir_cupon(_cupon(valor=Decimal("12.50"), num_cobros=1)) == "12.5% de descuento en el primer cobro"
    assert cobros.describir_cupon(_cupon(tipo="monto", valor=Decimal("1500"), num_cobros=3)) == \
        "$1,500 MXN de descuento en los primeros 3 cobros"
    assert cobros.describir_cupon(_cupon(tipo="meses_gratis", valor=Decimal("1"))) == "1 mes gratis"
    assert cobros.describir_cupon(_cupon(tipo="meses_gratis", valor=Decimal("3"))) == "3 meses gratis"


def test_sumar_meses_respeta_fin_de_mes():
    d = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
    assert cobros.sumar_meses(d, 1) == datetime(2026, 2, 28, 12, tzinfo=timezone.utc)
    assert cobros.sumar_meses(d, 13) == datetime(2027, 2, 28, 12, tzinfo=timezone.utc)
    assert cobros.sumar_meses(datetime(2026, 11, 15, tzinfo=timezone.utc), 3).month == 2


def test_esquema_de_cupon():
    with pytest.raises(ValidationError):
        CuponIn(codigo="TODO", tipo="porcentaje", valor=100)
    with pytest.raises(ValidationError):
        CuponIn(codigo="MEDIO", tipo="meses_gratis", valor=1.5)
    with pytest.raises(ValidationError):
        CuponIn(codigo="con espacio", tipo="monto", valor=100)
    # Los meses gratis no llevan número de cobros con descuento.
    assert CuponIn(codigo="ALIADO3", tipo="meses_gratis", valor=3, num_cobros=2).num_cobros is None


@pytest.mark.asyncio
async def test_cupon_valido_rechaza_vencido_agotado_y_repetido():
    async def probar(cupon, usos=0, ya_lo_uso=0):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_resultado(cupon))
        db.scalar = AsyncMock(side_effect=[usos, ya_lo_uso] if cupon is not None and cupon.max_usos else [ya_lo_uso])
        return await cobros.cupon_valido(db, " bienvenida ", "u1")

    with pytest.raises(cobros.CuponInvalido, match="no existe"):
        await probar(None)
    with pytest.raises(cobros.CuponInvalido, match="no existe"):
        await probar(_cupon(activo=False))
    with pytest.raises(cobros.CuponInvalido, match="venció"):
        await probar(_cupon(vigente_hasta=date.today() - timedelta(days=2)))
    with pytest.raises(cobros.CuponInvalido, match="límite"):
        await probar(_cupon(max_usos=5), usos=5)
    with pytest.raises(cobros.CuponInvalido, match="Ya usaste"):
        await probar(_cupon(), ya_lo_uso=1)
    assert (await probar(_cupon(max_usos=5), usos=4)).codigo == "BIENVENIDA"


def _db_para_crear(previas=None, cliente_previo=None):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_resultado(previas or []))
    db.scalar = AsyncMock(return_value=cliente_previo)
    db.add = MagicMock()
    return db


def _plan(precio="1000", meses=1):
    return PlanSuscripcion(nombre="Mensual", precio=Decimal(precio), moneda="MXN", intervalo_meses=meses, activo=True)


@pytest.mark.asyncio
async def test_crear_suscripcion_aplica_el_descuento(monkeypatch):
    cupon_st = AsyncMock(return_value="cpn_1")
    checkout = AsyncMock(return_value={"id": "cs_1", "url": "https://checkout.stripe.test/pagar"})
    monkeypatch.setattr(st, "crear_cupon", cupon_st)
    monkeypatch.setattr(st, "crear_checkout", checkout)
    db = _db_para_crear()

    sus = await cobros.crear_suscripcion(db, user_id="u1", email="a@b.com", plan=_plan(),
                                         cupon=_cupon(valor=Decimal("20"), num_cobros=3))

    assert sus.monto == Decimal("800.00") and sus.monto_regular == Decimal("1000.00")
    assert sus.cobros_con_descuento == 3 and sus.estado == "pendiente"
    assert sus.stripe_checkout_id == "cs_1" and sus.liga_pago == "https://checkout.stripe.test/pagar"
    # Stripe cobra el precio regular con un cupón que dura 3 cobros.
    assert cupon_st.await_args.kwargs | {"referencia": None} == {
        "referencia": None, "nombre": "BIENVENIDA", "tipo": "porcentaje", "valor": Decimal("20"),
        "moneda": "MXN", "num_cobros": 3, "cada_meses": 1}
    k = checkout.await_args.kwargs
    assert k["monto"] == Decimal("1000.00") and k["cupon_id"] == "cpn_1" and k["cliente_id"] is None
    assert k["exito_url"].endswith("/dashboard/datos?pago=listo")
    assert k["cancelar_url"].endswith("/dashboard/datos?pago=volver")
    db.add.assert_called_once_with(sus)


@pytest.mark.asyncio
async def test_sin_cupon_no_crea_cupon_y_reusa_el_cliente(monkeypatch):
    cupon_st = AsyncMock()
    checkout = AsyncMock(return_value={"id": "cs_2", "url": "x"})
    monkeypatch.setattr(st, "crear_cupon", cupon_st)
    monkeypatch.setattr(st, "crear_checkout", checkout)
    await cobros.crear_suscripcion(_db_para_crear(cliente_previo="cus_9"), user_id="u1", email="a@b.com",
                                   plan=_plan(meses=12), cupon=None)
    cupon_st.assert_not_awaited()
    assert checkout.await_args.kwargs["cliente_id"] == "cus_9"
    assert checkout.await_args.kwargs["cada_meses"] == 12 and checkout.await_args.kwargs["cupon_id"] is None


@pytest.mark.asyncio
async def test_crear_suscripcion_no_duplica_una_activa(monkeypatch):
    checkout = AsyncMock()
    monkeypatch.setattr(st, "crear_checkout", checkout)
    previa = Suscripcion(user_id="u1", email="a@b.com", estado="activa", stripe_subscription_id="sub_0")
    with pytest.raises(cobros.CuponInvalido, match="activa"):
        await cobros.crear_suscripcion(_db_para_crear([previa]), user_id="u1", email="a@b.com", plan=_plan(), cupon=None)
    checkout.assert_not_awaited()


@pytest.mark.asyncio
async def test_crear_suscripcion_cierra_la_pendiente_sin_pagar(monkeypatch):
    monkeypatch.setattr(st, "obtener_checkout", AsyncMock(return_value={"id": "cs_1", "status": "open"}))
    expirar = AsyncMock(return_value={})
    monkeypatch.setattr(st, "expirar_checkout", expirar)
    monkeypatch.setattr(st, "crear_checkout", AsyncMock(return_value={"id": "cs_2", "url": "x"}))
    previa = Suscripcion(user_id="u1", email="a@b.com", estado="pendiente", stripe_checkout_id="cs_1")

    await cobros.crear_suscripcion(_db_para_crear([previa]), user_id="u1", email="a@b.com", plan=_plan(), cupon=None)

    assert previa.estado == "cancelada"
    expirar.assert_awaited_once_with("cs_1")


@pytest.mark.asyncio
async def test_pendiente_que_ya_se_pago_no_se_duplica(monkeypatch):
    """El webhook no llegó pero en Stripe ya se pagó: se detecta y no se abre otra."""
    monkeypatch.setattr(st, "obtener_checkout", AsyncMock(return_value={
        "id": "cs_1", "status": "complete", "subscription": "sub_1", "customer": "cus_1"}))
    monkeypatch.setattr(st, "obtener_suscripcion", AsyncMock(return_value={"status": "active", "customer": "cus_1"}))
    checkout = AsyncMock()
    monkeypatch.setattr(st, "crear_checkout", checkout)
    previa = Suscripcion(user_id="u1", email="a@b.com", estado="pendiente", stripe_checkout_id="cs_1")
    db = _db_para_crear([previa])
    with pytest.raises(cobros.CuponInvalido, match="activa"):
        await cobros.crear_suscripcion(db, user_id="u1", email="a@b.com", plan=_plan(), cupon=None)
    assert previa.estado == "activa" and previa.stripe_subscription_id == "sub_1"
    checkout.assert_not_awaited()


@pytest.mark.asyncio
async def test_crear_suscripcion_rechaza_meses_gratis_y_cobro_en_cero(monkeypatch):
    monkeypatch.setattr(st, "crear_checkout", AsyncMock())
    plan = _plan(precio="300")
    with pytest.raises(cobros.CuponInvalido, match="meses gratis"):
        await cobros.crear_suscripcion(_db_para_crear(), user_id="u1", email="a@b.com", plan=plan,
                                       cupon=_cupon(tipo="meses_gratis", valor=Decimal("2")))
    with pytest.raises(cobros.CuponInvalido, match=r"\$0"):
        await cobros.crear_suscripcion(_db_para_crear(), user_id="u1", email="a@b.com", plan=plan,
                                       cupon=_cupon(tipo="monto", valor=Decimal("300")))


def _sus_con_descuento(restantes):
    return Suscripcion(user_id="u1", email="a@b.com", estado="activa", stripe_subscription_id="sub_1",
                       monto=Decimal("800"), monto_regular=Decimal("1000"), moneda="MXN",
                       intervalo_meses=1, cobros_con_descuento=restantes)


_FACTURA = {"id": "in_77", "subscription": "sub_1", "amount_paid": 80000, "amount_due": 80000, "currency": "mxn",
            "status": "paid", "billing_reason": "subscription_cycle", "attempt_count": 1,
            "status_transitions": {"paid_at": 1793534400}, "created": 1793541000}


@pytest.mark.asyncio
async def test_al_agotarse_el_descuento_se_muestra_el_precio_regular():
    sus = _sus_con_descuento(1)
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_resultado(sus), _resultado(None)])
    db.add = MagicMock()

    pago = await cobros.registrar_pago(db, _FACTURA, "pagado")

    assert isinstance(pago, Pago) and pago.estado == "pagado" and pago.monto == Decimal("800.00")
    assert pago.moneda == "MXN" and pago.fecha == datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
    assert sus.monto == Decimal("1000") and sus.cobros_con_descuento is None


@pytest.mark.asyncio
async def test_factura_con_la_forma_nueva_de_stripe():
    """En versiones recientes de la API la suscripción viene en parent.subscription_details."""
    sus = _sus_con_descuento(None)
    factura = {k: v for k, v in _FACTURA.items() if k != "subscription"} | {
        "parent": {"type": "subscription_details", "subscription_details": {"subscription": "sub_1"}}}
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_resultado(sus), _resultado(None)])
    db.add = MagicMock()
    assert (await cobros.registrar_pago(db, factura, "pagado")).stripe_invoice_id == "in_77"


@pytest.mark.asyncio
async def test_un_aviso_repetido_no_descuenta_dos_veces():
    sus = _sus_con_descuento(2)
    ya = Pago(user_id="u1", stripe_invoice_id="in_77", monto=Decimal("800"), moneda="MXN", estado="pagado")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_resultado(sus), _resultado(ya)])
    db.add = MagicMock()

    await cobros.registrar_pago(db, _FACTURA, "pagado")

    assert sus.cobros_con_descuento == 2
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_un_fallo_atrasado_no_deshace_un_pago():
    sus = _sus_con_descuento(None)
    ya = Pago(user_id="u1", stripe_invoice_id="in_77", monto=Decimal("800"), moneda="MXN", estado="pagado")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_resultado(sus), _resultado(ya)])
    await cobros.registrar_pago(db, _FACTURA, "fallido")
    assert ya.estado == "pagado"


@pytest.mark.asyncio
async def test_factura_en_cero_no_es_un_cobro():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_resultado(_sus_con_descuento(None)))
    db.add = MagicMock()
    assert await cobros.registrar_pago(db, _FACTURA | {"amount_paid": 0}, "pagado") is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_sincronizar_activa_gasta_el_cupon():
    sus = Suscripcion(user_id="u1", email="a@b.com", estado="pendiente", stripe_subscription_id="sub_1",
                      liga_pago="https://checkout.stripe.test/pagar")
    sus.cupon_id = _cupon().id
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    db.add = MagicMock()

    # Forma nueva de la API: el fin del periodo viene en las partidas.
    await cobros.sincronizar_suscripcion(db, sus, {"status": "active", "customer": "cus_1",
                                                  "items": {"data": [{"current_period_end": 1796212800}]}})

    assert sus.estado == "activa" and sus.liga_pago is None and sus.stripe_customer_id == "cus_1"
    assert sus.proximo_cobro == datetime(2026, 12, 2, 12, tzinfo=timezone.utc) and sus.vence is None
    canje = db.add.call_args.args[0]
    assert canje.cupon_id == sus.cupon_id and canje.user_id == "u1"


@pytest.mark.asyncio
async def test_cancelada_al_final_conserva_el_acceso_hasta_el_fin_del_periodo():
    sus = Suscripcion(user_id="u1", email="a@b.com", estado="activa", stripe_subscription_id="sub_1",
                      monto=Decimal("1000"), monto_regular=Decimal("1000"))
    await cobros.sincronizar_suscripcion(AsyncMock(), sus, {
        "status": "active", "cancel_at_period_end": True, "current_period_end": 1796212800})
    assert sus.estado == "activa" and sus.proximo_cobro is None
    assert sus.vence == datetime(2026, 12, 2, 12, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_cobro_fallido_pausa_y_checkout_vencido_cancela(monkeypatch):
    sus = Suscripcion(user_id="u1", email="a@b.com", estado="activa", stripe_subscription_id="sub_1",
                      monto=Decimal("1000"), monto_regular=Decimal("1000"))
    await cobros.sincronizar_suscripcion(AsyncMock(), sus, {"status": "past_due", "current_period_end": 1796212800})
    assert sus.estado == "pausada"

    monkeypatch.setattr(st, "obtener_checkout", AsyncMock(return_value={"id": "cs_1", "status": "expired"}))
    pendiente = Suscripcion(user_id="u1", email="a@b.com", estado="pendiente", stripe_checkout_id="cs_1", liga_pago="x")
    await cobros.sincronizar_suscripcion(AsyncMock(), pendiente)
    assert pendiente.estado == "cancelada" and pendiente.liga_pago is None


@pytest.mark.asyncio
async def test_meses_gratis_se_suman_a_la_cortesia_vigente(monkeypatch):
    vence = datetime.now(timezone.utc) + timedelta(days=10)
    actual = Suscripcion(user_id="u1", email="a@b.com", estado="cortesia", vence=vence)
    monkeypatch.setattr(cobros, "suscripcion_actual", AsyncMock(return_value=actual))
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    db.add = MagicMock()

    sus = await cobros.canjear_meses_gratis(db, user_id="u1", email="a@b.com",
                                            cupon=_cupon(tipo="meses_gratis", valor=Decimal("2")))

    assert sus is actual and sus.vence == cobros.sumar_meses(vence, 2)
    db.add.assert_called_once()  # solo el canje


def _firmar(cuerpo: bytes, t: int, secreto: str = "whsec_x") -> str:
    v1 = hmac.new(secreto.encode(), f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"


def test_firma_del_webhook(monkeypatch):
    monkeypatch.setattr(st.settings, "STRIPE_WEBHOOK_SECRET", "whsec_x")
    cuerpo = b'{"id": "evt_1"}'
    assert st.firma_valida(cuerpo, _firmar(cuerpo, 1000), ahora=1100)
    assert not st.firma_valida(cuerpo + b" ", _firmar(cuerpo, 1000), ahora=1100)  # cuerpo alterado
    assert not st.firma_valida(cuerpo, _firmar(cuerpo, 1000), ahora=1000 + 301)  # aviso viejo
    assert not st.firma_valida(cuerpo, _firmar(cuerpo, 1000, "otro"), ahora=1100)
    assert not st.firma_valida(cuerpo, None, ahora=1100)
    monkeypatch.setattr(st.settings, "STRIPE_WEBHOOK_SECRET", "")
    assert not st.firma_valida(cuerpo, _firmar(cuerpo, 1000), ahora=1100)


def test_formulario_de_stripe():
    assert st.aplanar({"mode": "subscription", "customer": None, "line_items": [
        {"quantity": 1, "price_data": {"recurring": {"interval": "month"}}}], "x": True}) == [
        ("mode", "subscription"), ("line_items[0][quantity]", "1"),
        ("line_items[0][price_data][recurring][interval]", "month"), ("x", "true")]
    assert st.centavos(Decimal("2499.99")) == 249999 and st.centavos(1000) == 100000


@pytest.mark.asyncio
async def test_duracion_del_cupon_de_stripe(monkeypatch):
    pedir = AsyncMock(return_value={"id": "cpn"})
    monkeypatch.setattr(st, "_pedir", pedir)
    base = dict(referencia="r", nombre="HOLA", moneda="MXN")
    await st.crear_cupon(**base, tipo="porcentaje", valor=Decimal("12.50"), num_cobros=2, cada_meses=12)
    datos = pedir.await_args.args[2]
    assert datos["percent_off"] == "12.5" and datos["duration"] == "repeating" and datos["duration_in_months"] == 24
    await st.crear_cupon(**base, tipo="monto", valor=Decimal("300"), num_cobros=1, cada_meses=1)
    datos = pedir.await_args.args[2]
    assert datos["amount_off"] == 30000 and datos["currency"] == "mxn" and datos["duration"] == "once"
    await st.crear_cupon(**base, tipo="monto", valor=Decimal("300"), num_cobros=None, cada_meses=1)
    assert pedir.await_args.args[2]["duration"] == "forever"


def test_modo_segun_la_clave(monkeypatch):
    monkeypatch.setattr(st.settings, "STRIPE_SECRET_KEY", "sk_test_abc")
    assert st.modo() == "prueba"
    monkeypatch.setattr(st.settings, "STRIPE_SECRET_KEY", "sk_live_abc")
    assert st.modo() == "produccion"
    monkeypatch.setattr(st.settings, "STRIPE_SECRET_KEY", "")
    assert st.modo() is None and not st.configurado()


@pytest.mark.asyncio
async def test_quien_ya_paga_no_canjea_meses_gratis(monkeypatch):
    activa = Suscripcion(user_id="u1", email="a@b.com", estado="activa")
    monkeypatch.setattr(cobros, "suscripcion_actual", AsyncMock(return_value=activa))
    db = AsyncMock()
    db.add = MagicMock()
    with pytest.raises(cobros.CuponInvalido, match="suscripción de pago"):
        await cobros.canjear_meses_gratis(db, user_id="u1", email="a@b.com",
                                          cupon=_cupon(tipo="meses_gratis", valor=Decimal("2")))
    db.add.assert_not_called()
