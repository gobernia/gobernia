"""Cliente mínimo de Stripe: Checkout para suscribirse, portal del cliente, suscripciones
y la firma de los webhooks. Sin SDK: la API de Stripe es REST con formularios.

La tarjeta nunca pasa por Gobernia: el cliente paga en la página de Stripe (Checkout) y
administra su tarjeta en el portal de Stripe.

Stripe cambió de lugar algunos campos entre versiones de su API (p. ej. el fin del
periodo pasó de la suscripción a sus partidas, y la suscripción de una factura pasó a
`parent`). No fijamos versión: los lectores de abajo aceptan ambas formas.
"""
import hashlib
import hmac
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from decimal import Decimal

import httpx

from app.core.config import settings

API = "https://api.stripe.com/v1"
# Un aviso firmado hace más de 5 minutos se rechaza: evita que alguien lo repita.
TOLERANCIA_FIRMA = 300


class StripeError(Exception):
    pass


def configurado() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def modo() -> str | None:
    """Las claves de prueba (sk_test_…, rk_test_…) no hacen cobros reales."""
    if not configurado():
        return None
    return "prueba" if "_test_" in settings.STRIPE_SECRET_KEY else "produccion"


def clave_publica() -> str | None:
    """La clave publicable para mostrar el pago dentro de gobernia.ai, solo si es del mismo
    modo (prueba/real) que la secreta: mezclarlas haría fallar el pago."""
    pk = settings.STRIPE_PUBLISHABLE_KEY.strip()
    if not configurado() or not pk.startswith("pk_"):
        return None
    if ("_test_" in pk) != (modo() == "prueba"):
        return None
    return pk


def centavos(monto) -> int:
    return int((Decimal(str(monto)) * 100).to_integral_value())


def _texto(v) -> str:
    return ("true" if v else "false") if isinstance(v, bool) else str(v)


def aplanar(datos: dict, prefijo: str = "") -> list[tuple[str, str]]:
    """{"a": {"b": 1}, "c": [{"d": 2}]} → [("a[b]", "1"), ("c[0][d]", "2")], el formato
    de formularios de Stripe. Los None se omiten."""
    pares: list[tuple[str, str]] = []
    for k, v in datos.items():
        clave = f"{prefijo}[{k}]" if prefijo else str(k)
        if v is None:
            continue
        if isinstance(v, dict):
            pares += aplanar(v, clave)
        elif isinstance(v, (list, tuple)):
            for i, item in enumerate(v):
                sub = f"{clave}[{i}]"
                pares += aplanar(item, sub) if isinstance(item, dict) else [(sub, _texto(item))]
        else:
            pares.append((clave, _texto(v)))
    return pares


async def _pedir(metodo: str, ruta: str, datos: dict | None = None, idempotencia: str | None = None) -> dict:
    if not configurado():
        raise StripeError("Stripe no está configurado.")
    headers = {"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"}
    if idempotencia:
        headers["Idempotency-Key"] = idempotencia
    cuerpo = None
    if datos:
        # El formulario se codifica aquí: httpx no acepta una lista de pares en `data`
        # (la toma como contenido síncrono y el cliente asíncrono la rechaza).
        cuerpo = urlencode(aplanar(datos))
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    async with httpx.AsyncClient(base_url=API, timeout=20) as c:
        r = await c.request(metodo, ruta, content=cuerpo, headers=headers)
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message") or r.text
        except ValueError:
            msg = r.text
        raise StripeError(f"Stripe respondió {r.status_code}: {str(msg)[:300]}")
    return r.json()


def _recurrencia(cada_meses: int) -> dict:
    return {"interval": "year", "interval_count": 1} if cada_meses == 12 else {"interval": "month", "interval_count": cada_meses}


async def crear_cupon(*, referencia: str, nombre: str, tipo: str, valor, moneda: str,
                      num_cobros: int | None, cada_meses: int) -> str:
    """Cupón de Stripe de un solo uso con el descuento de nuestro cupón. Stripe lo quita
    solo cuando se cumple su duración: `num_cobros` cobros del plan (None = siempre)."""
    datos: dict = {"name": nombre[:40], "max_redemptions": 1, "metadata": {"suscripcion_id": referencia}}
    if tipo == "porcentaje":
        datos["percent_off"] = f"{Decimal(str(valor)).normalize():f}"
    else:
        datos["amount_off"] = centavos(valor)
        datos["currency"] = moneda.lower()
    if num_cobros is None:
        datos["duration"] = "forever"
    elif num_cobros == 1:
        datos["duration"] = "once"
    else:
        datos["duration"] = "repeating"
        datos["duration_in_months"] = num_cobros * cada_meses
    return (await _pedir("POST", "/coupons", datos, idempotencia=f"cupon-{referencia}"))["id"]


async def crear_checkout(
    *, referencia: str, email: str, cliente_id: str | None, nombre: str, monto, moneda: str,
    cada_meses: int, cupon_id: str | None, exito_url: str, cancelar_url: str, incrustado: bool = False,
) -> dict:
    """Página de pago de Stripe para una suscripción. El precio es el regular; el descuento
    va en el cupón. Devuelve la sesión: con `incrustado` trae `client_secret` para mostrar
    el pago dentro de gobernia.ai; si no, `url` es la liga a la página de Stripe."""
    if incrustado:
        destinos = [{"ui_mode": "embedded_page", "return_url": exito_url},
                    # Cuentas con una versión de la API anterior al 2026-03-25 usan el nombre viejo.
                    {"ui_mode": "embedded", "return_url": exito_url}]
    else:
        destinos = [{"success_url": exito_url, "cancel_url": cancelar_url}]
    for i, destino in enumerate(destinos):
        try:
            return await _sesion_de_pago(referencia, email, cliente_id, nombre, monto, moneda, cada_meses,
                                         cupon_id, destino)
        except StripeError as e:
            # Un parámetro rechazado no queda guardado con la llave de idempotencia: se puede reintentar.
            if i == len(destinos) - 1 or "ui_mode" not in str(e):
                raise
    raise StripeError("Sin destino para la sesión de pago.")  # inalcanzable


async def _sesion_de_pago(referencia, email, cliente_id, nombre, monto, moneda, cada_meses, cupon_id,
                          destino: dict) -> dict:
    return await _pedir("POST", "/checkout/sessions", {
        "mode": "subscription",
        "client_reference_id": referencia,
        "customer": cliente_id,
        "customer_email": None if cliente_id else email,
        "line_items": [{
            "quantity": 1,
            "price_data": {
                "currency": moneda.lower(),
                "unit_amount": centavos(monto),
                "recurring": _recurrencia(cada_meses),
                "product_data": {"name": nombre},
            },
        }],
        "discounts": [{"coupon": cupon_id}] if cupon_id else None,
        "metadata": {"suscripcion_id": referencia},
        "subscription_data": {"metadata": {"suscripcion_id": referencia}},
        "locale": "es-419",
        **destino,
    }, idempotencia=f"checkout-{referencia}")


async def obtener_checkout(sesion_id: str) -> dict:
    return await _pedir("GET", f"/checkout/sessions/{sesion_id}")


async def expirar_checkout(sesion_id: str) -> dict:
    """Cierra una liga de pago que el cliente no usó."""
    return await _pedir("POST", f"/checkout/sessions/{sesion_id}/expire")


async def obtener_suscripcion(sub_id: str) -> dict:
    return await _pedir("GET", f"/subscriptions/{sub_id}")


async def cancelar_al_final(sub_id: str) -> dict:
    """Ya no se renueva; el cliente conserva el acceso hasta el fin del periodo pagado."""
    return await _pedir("POST", f"/subscriptions/{sub_id}", {"cancel_at_period_end": True})


async def crear_portal(cliente_id: str, regreso_url: str) -> dict:
    """Portal de Stripe donde el cliente cambia su tarjeta y ve sus facturas."""
    return await _pedir("POST", "/billing_portal/sessions", {"customer": cliente_id, "return_url": regreso_url})


async def obtener_evento(evento_id: str) -> dict:
    return await _pedir("GET", f"/events/{evento_id}")


def firma_valida(cuerpo: bytes, encabezado: str | None, ahora: float | None = None) -> bool:
    """Valida el encabezado Stripe-Signature (t=…,v1=…): HMAC-SHA256 de "t.cuerpo" con el
    secreto del webhook, y que no tenga más de TOLERANCIA_FIRMA segundos."""
    secreto = settings.STRIPE_WEBHOOK_SECRET
    if not secreto:
        return False
    partes = [p.strip().split("=", 1) for p in (encabezado or "").split(",") if "=" in p]
    t = next((v for k, v in partes if k == "t"), None)
    firmas = [v for k, v in partes if k == "v1"]
    if not t or not t.isdigit() or not firmas:
        return False
    if abs((ahora if ahora is not None else time.time()) - int(t)) > TOLERANCIA_FIRMA:
        return False
    esperado = hmac.new(secreto.encode(), f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(esperado, f) for f in firmas)


# ── Lectores que aceptan las distintas versiones de la API ────────────────────

def fecha(ts) -> datetime | None:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else None


def fin_del_periodo(sub: dict) -> datetime | None:
    ts = sub.get("current_period_end")
    if ts is None:
        partidas = (sub.get("items") or {}).get("data") or []
        ts = partidas[0].get("current_period_end") if partidas else None
    return fecha(ts)


def tiene_descuento(sub: dict) -> bool:
    return bool(sub.get("discount") or sub.get("discounts"))


def _id(v) -> str | None:
    if isinstance(v, dict):
        return v.get("id")
    return v or None


def suscripcion_de_factura(factura: dict) -> str | None:
    sub = _id(factura.get("subscription"))
    if sub:
        return sub
    detalles = ((factura.get("parent") or {}).get("subscription_details") or {})
    return _id(detalles.get("subscription"))
