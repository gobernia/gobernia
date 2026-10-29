"""Cliente mínimo de Mercado Pago: suscripciones (preapproval) y sus cobros periódicos.

La verdad siempre se lee de la API con nuestro token. El webhook solo avisa que algo
cambió; por eso, aunque alguien falsifique una notificación, solo provoca una lectura.
"""
import hashlib
import hmac

import httpx

from app.core.config import settings

API = "https://api.mercadopago.com"


class MercadoPagoError(Exception):
    pass


def configurado() -> bool:
    return bool(settings.MERCADOPAGO_ACCESS_TOKEN)


async def _pedir(metodo: str, ruta: str, cuerpo: dict | None = None, idempotencia: str | None = None) -> dict:
    if not configurado():
        raise MercadoPagoError("Mercado Pago no está configurado.")
    headers = {"Authorization": f"Bearer {settings.MERCADOPAGO_ACCESS_TOKEN}"}
    if idempotencia:
        headers["X-Idempotency-Key"] = idempotencia
    async with httpx.AsyncClient(base_url=API, timeout=20) as c:
        r = await c.request(metodo, ruta, json=cuerpo, headers=headers)
    if r.status_code >= 400:
        raise MercadoPagoError(f"Mercado Pago respondió {r.status_code}: {r.text[:300]}")
    return r.json()


async def crear_suscripcion(
    *, referencia: str, email: str, motivo: str, monto: float, moneda: str, cada_meses: int, back_url: str,
) -> dict:
    """Suscripción sin plan y con pago pendiente: devuelve `init_point`, la liga donde
    el cliente captura su tarjeta en Mercado Pago."""
    return await _pedir("POST", "/preapproval", {
        "reason": motivo,
        "external_reference": referencia,
        "payer_email": email,
        "auto_recurring": {
            "frequency": cada_meses,
            "frequency_type": "months",
            "transaction_amount": monto,
            "currency_id": moneda,
        },
        "back_url": back_url,
        "status": "pending",
    }, idempotencia=referencia)


async def obtener_suscripcion(preapproval_id: str) -> dict:
    return await _pedir("GET", f"/preapproval/{preapproval_id}")


async def cancelar_suscripcion(preapproval_id: str) -> dict:
    return await _pedir("PUT", f"/preapproval/{preapproval_id}", {"status": "cancelled"})


async def cambiar_monto(preapproval_id: str, monto: float, moneda: str) -> dict:
    return await _pedir("PUT", f"/preapproval/{preapproval_id}", {
        "auto_recurring": {"transaction_amount": monto, "currency_id": moneda},
    })


async def obtener_cobro(authorized_payment_id: str) -> dict:
    return await _pedir("GET", f"/authorized_payments/{authorized_payment_id}")


def firma_valida(x_signature: str | None, x_request_id: str | None, data_id: str | None) -> bool:
    """Valida el encabezado x-signature del webhook (HMAC-SHA256 con la clave secreta).
    Sin clave configurada se acepta: igual solo se lee de la API con nuestro token."""
    secreto = settings.MERCADOPAGO_WEBHOOK_SECRET
    if not secreto:
        return True
    partes = dict(p.strip().split("=", 1) for p in (x_signature or "").split(",") if "=" in p)
    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1:
        return False
    manifiesto = ""
    if data_id:
        manifiesto += f"id:{data_id.lower() if data_id.isalnum() else data_id};"
    if x_request_id:
        manifiesto += f"request-id:{x_request_id};"
    manifiesto += f"ts:{ts};"
    esperado = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)
