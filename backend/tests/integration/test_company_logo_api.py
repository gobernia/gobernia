"""Ciclo completo del logo: POST → GET (data URL) → DELETE → GET (has_logo false)."""
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from PIL import Image

from app.core.dependencies import get_current_user_id, get_db
from app.main import app

USER = "user-logo-1"


def _png(width: int = 100, height: int = 50) -> bytes:
    buf = BytesIO()
    Image.new("RGBA", (width, height), (10, 20, 30, 255)).save(buf, format="PNG")
    return buf.getvalue()


class FakeDB:
    """DB en memoria mínima para el CRUD del logo (una fila por usuario)."""

    def __init__(self):
        self.rows: list = []

    async def execute(self, _stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = self.rows[0] if self.rows else None
        return res

    def add(self, row):
        self.rows.append(row)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def delete(self, row):
        self.rows.remove(row)


def _overrides(db):
    async def _db():
        yield db
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user_id] = lambda: USER


@pytest.mark.asyncio
async def test_ciclo_completo_post_get_delete():
    db = FakeDB()
    _overrides(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            # Antes de subir nada: no hay logo.
            r = await c.get("/api/v1/company/logo")
            assert r.status_code == 200
            assert r.json() == {"has_logo": False, "logo": None}

            # POST (multipart)
            r = await c.post("/api/v1/company/logo",
                             files={"file": ("logo.png", _png(), "image/png")})
            assert r.status_code == 200
            body = r.json()
            assert body["has_logo"] is True
            assert body["logo"].startswith("data:image/png;base64,")
            assert len(db.rows) == 1

            # GET devuelve la data URL
            r = await c.get("/api/v1/company/logo")
            assert r.status_code == 200
            assert r.json()["has_logo"] is True
            assert r.json()["logo"].startswith("data:image/png;base64,")

            # DELETE
            r = await c.delete("/api/v1/company/logo")
            assert r.status_code == 200
            assert r.json() == {"has_logo": False}
            assert db.rows == []

            # GET tras borrar
            r = await c.get("/api/v1/company/logo")
            assert r.json() == {"has_logo": False, "logo": None}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_subir_dos_veces_deja_un_solo_registro():
    db = FakeDB()
    _overrides(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/api/v1/company/logo", files={"file": ("a.png", _png(60, 60), "image/png")})
            r = await c.post("/api/v1/company/logo", files={"file": ("b.png", _png(80, 40), "image/png")})
        assert r.status_code == 200
        assert len(db.rows) == 1
        img = Image.open(BytesIO(db.rows[0].data))
        assert (img.width, img.height) == (80, 40)  # se guardó el segundo
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("nombre,contenido", [
    ("logo.gif", _png()),                     # extensión no permitida
    ("logo.png", b"esto no es una imagen"),   # miente sobre su tipo
    ("logo.png", b"\x89PNG" + b"x" * (1024 * 1024 + 1)),  # > 1 MB
])
async def test_uploads_invalidos_devuelven_400(nombre, contenido):
    db = FakeDB()
    _overrides(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/company/logo",
                             files={"file": (nombre, contenido, "image/png")})
        assert r.status_code == 400
        assert db.rows == []
    finally:
        app.dependency_overrides.clear()
