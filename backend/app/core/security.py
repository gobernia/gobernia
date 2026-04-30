import time
import httpx
from jose import jwt, JWTError, ExpiredSignatureError
from fastapi import HTTPException, status

from app.core.config import settings

# Fallback: clave pública EC de Supabase (se actualiza si JWKS fetch tiene éxito)
_SUPABASE_FALLBACK_JWK = {
    "alg": "ES256",
    "crv": "P-256",
    "kid": "92d27aaf-5217-4d0d-9dcb-8eb2bf3e68d1",
    "kty": "EC",
    "use": "sig",
    "x": "SWS5i8YOInJ8QDsb9lfQlsiXsIyY0rcjHmtPpUjZaoI",
    "y": "L8rAP8J3nCtbCQNScI5uKggNhYi7gjiK-4swCRD9sgg",
}

_jwks_cache: tuple[dict, float] | None = None
_JWKS_TTL = 3600


def _fetch_jwks() -> dict:
    global _jwks_cache
    now = time.monotonic()
    if _jwks_cache and (now - _jwks_cache[1]) < _JWKS_TTL:
        return _jwks_cache[0]

    url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        keys_by_kid = {k["kid"]: k for k in data.get("keys", [])}
        _jwks_cache = (keys_by_kid, now)
        return keys_by_kid
    except Exception:
        # Usa la clave hardcodeada como fallback
        return {_SUPABASE_FALLBACK_JWK["kid"]: _SUPABASE_FALLBACK_JWK}


def verify_supabase_token(token: str) -> dict:
    """Verifica el JWT de Supabase y retorna el payload decodificado."""
    if not settings.SUPABASE_URL:
        return {"sub": "dev-user", "email": "dev@gobernia.com"}

    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token malformado")

    kid = header.get("kid")
    alg = header.get("alg", "ES256")

    keys = _fetch_jwks()

    if kid and kid in keys:
        public_key = keys[kid]
    elif keys:
        public_key = next(iter(keys.values()))
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clave pública no encontrada")

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[alg],
            options={"verify_aud": False},
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token inválido: {e}")
