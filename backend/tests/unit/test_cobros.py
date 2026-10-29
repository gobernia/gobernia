"""Reglas de cobro: cupones, precios, descuentos por tiempo limitado y firma del webhook."""
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
from app.services.pagos import mercadopago as mp


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


@pytest.mark.asyncio
async def test_crear_suscripcion_aplica_el_descuento(monkeypatch):
    crear = AsyncMock(return_value={"id": "pre-1", "init_point": "https://mp.test/pagar"})
    monkeypatch.setattr(mp, "crear_suscripcion", crear)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_resultado([]))
    db.add = MagicMock()
    plan = PlanSuscripcion(nombre="Mensual", precio=Decimal("1000"), moneda="MXN", intervalo_meses=1, activo=True)

    sus = await cobros.crear_suscripcion(db, user_id="u1", email="a@b.com", plan=plan,
                                         cupon=_cupon(valor=Decimal("20"), num_cobros=3))

    assert sus.monto == Decimal("800.00") and sus.monto_regular == Decimal("1000.00")
    assert sus.cobros_con_descuento == 3 and sus.estado == "pendiente"
    assert sus.mp_preapproval_id == "pre-1" and sus.mp_init_point == "https://mp.test/pagar"
    assert crear.await_args.kwargs["monto"] == 800.0
    assert crear.await_args.kwargs["back_url"].endswith("/dashboard/suscripcion")
    db.add.assert_called_once_with(sus)


@pytest.mark.asyncio
async def test_crear_suscripcion_no_duplica_una_activa(monkeypatch):
    monkeypatch.setattr(mp, "crear_suscripcion", AsyncMock())
    previa = Suscripcion(user_id="u1", email="a@b.com", estado="activa", mp_preapproval_id="pre-0")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_resultado([previa]))
    plan = PlanSuscripcion(nombre="Mensual", precio=Decimal("1000"), moneda="MXN", intervalo_meses=1, activo=True)
    with pytest.raises(cobros.CuponInvalido, match="activa"):
        await cobros.crear_suscripcion(db, user_id="u1", email="a@b.com", plan=plan, cupon=None)
    mp.crear_suscripcion.assert_not_awaited()


@pytest.mark.asyncio
async def test_crear_suscripcion_cierra_la_pendiente_sin_pagar(monkeypatch):
    monkeypatch.setattr(mp, "obtener_suscripcion", AsyncMock(return_value={"status": "pending"}))
    cancelar = AsyncMock(return_value={})
    monkeypatch.setattr(mp, "cancelar_suscripcion", cancelar)
    monkeypatch.setattr(mp, "crear_suscripcion", AsyncMock(return_value={"id": "pre-2", "init_point": "x"}))
    previa = Suscripcion(user_id="u1", email="a@b.com", estado="pendiente", mp_preapproval_id="pre-1")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_resultado([previa]))
    db.add = MagicMock()
    plan = PlanSuscripcion(nombre="Mensual", precio=Decimal("1000"), moneda="MXN", intervalo_meses=1, activo=True)

    await cobros.crear_suscripcion(db, user_id="u1", email="a@b.com", plan=plan, cupon=None)

    assert previa.estado == "cancelada"
    cancelar.assert_awaited_once_with("pre-1")


@pytest.mark.asyncio
async def test_crear_suscripcion_rechaza_meses_gratis_y_cobro_en_cero(monkeypatch):
    monkeypatch.setattr(mp, "crear_suscripcion", AsyncMock())
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_resultado([]))
    plan = PlanSuscripcion(nombre="Mensual", precio=Decimal("300"), moneda="MXN", intervalo_meses=1, activo=True)
    with pytest.raises(cobros.CuponInvalido, match="meses gratis"):
        await cobros.crear_suscripcion(db, user_id="u1", email="a@b.com", plan=plan,
                                       cupon=_cupon(tipo="meses_gratis", valor=Decimal("2")))
    with pytest.raises(cobros.CuponInvalido, match=r"\$0"):
        await cobros.crear_suscripcion(db, user_id="u1", email="a@b.com", plan=plan,
                                       cupon=_cupon(tipo="monto", valor=Decimal("300")))


def _sus_con_descuento(restantes):
    return Suscripcion(user_id="u1", email="a@b.com", estado="activa", mp_preapproval_id="pre-1",
                       monto=Decimal("800"), monto_regular=Decimal("1000"), moneda="MXN",
                       intervalo_meses=1, cobros_con_descuento=restantes)


_COBRO = {"id": 77, "preapproval_id": "pre-1", "transaction_amount": 800, "currency_id": "MXN",
          "status": "processed", "debit_date": "2026-11-01T10:00:00.000-06:00",
          "payment": {"id": 9, "status": "approved"}}


@pytest.mark.asyncio
async def test_al_agotarse_el_descuento_se_cobra_el_precio_regular(monkeypatch):
    cambiar = AsyncMock(return_value={})
    monkeypatch.setattr(mp, "cambiar_monto", cambiar)
    sus = _sus_con_descuento(1)
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_resultado(sus), _resultado(None)])
    db.add = MagicMock()

    pago = await cobros.registrar_cobro(db, _COBRO)

    assert isinstance(pago, Pago) and pago.estado == "approved" and pago.monto == Decimal("800.00")
    assert pago.fecha == datetime(2026, 11, 1, 16, tzinfo=timezone.utc)
    cambiar.assert_awaited_once_with("pre-1", 1000.0, "MXN")
    assert sus.monto == Decimal("1000") and sus.cobros_con_descuento is None


@pytest.mark.asyncio
async def test_un_aviso_repetido_no_descuenta_dos_veces(monkeypatch):
    cambiar = AsyncMock()
    monkeypatch.setattr(mp, "cambiar_monto", cambiar)
    sus = _sus_con_descuento(2)
    ya = Pago(user_id="u1", mp_id="77", monto=Decimal("800"), moneda="MXN", estado="approved")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_resultado(sus), _resultado(ya)])
    db.add = MagicMock()

    await cobros.registrar_cobro(db, _COBRO)

    assert sus.cobros_con_descuento == 2
    cambiar.assert_not_awaited()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_sincronizar_activa_gasta_el_cupon():
    sus = Suscripcion(user_id="u1", email="a@b.com", estado="pendiente", mp_preapproval_id="pre-1",
                      mp_init_point="https://mp.test/pagar")
    sus.cupon_id = _cupon().id
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    db.add = MagicMock()

    await cobros.sincronizar_suscripcion(db, sus, {"status": "authorized",
                                                  "next_payment_date": "2026-12-01T00:00:00.000-06:00"})

    assert sus.estado == "activa" and sus.mp_init_point is None
    assert sus.proximo_cobro == datetime(2026, 12, 1, 6, tzinfo=timezone.utc)
    canje = db.add.call_args.args[0]
    assert canje.cupon_id == sus.cupon_id and canje.user_id == "u1"


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


def test_firma_del_webhook(monkeypatch):
    monkeypatch.setattr(mp.settings, "MERCADOPAGO_WEBHOOK_SECRET", "secreto")
    manifiesto = "id:pre1;request-id:req-9;ts:1704908010;"
    v1 = hmac.new(b"secreto", manifiesto.encode(), hashlib.sha256).hexdigest()
    assert mp.firma_valida(f"ts=1704908010,v1={v1}", "req-9", "PRE1")
    assert not mp.firma_valida(f"ts=1704908010,v1={v1}", "otra", "PRE1")
    assert not mp.firma_valida(None, "req-9", "PRE1")
    monkeypatch.setattr(mp.settings, "MERCADOPAGO_WEBHOOK_SECRET", "")
    assert mp.firma_valida(None, None, None)


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
