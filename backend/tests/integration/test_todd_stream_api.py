"""Todd en vivo: la respuesta llega por eventos (NDJSON) y el turno se guarda al final."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

R = "app.api.v1.todd_secretario.router"


class _SesionFalsa:
    def __init__(self, guardados):
        self.guardados = guardados

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def add(self, obj):
        self.guardados.append(obj)

    async def commit(self):
        pass


@pytest.mark.asyncio
async def test_stream_emite_texto_leyendo_y_fin_y_guarda_el_turno(monkeypatch):
    guardados = []

    async def anchor(uid, db):
        return "00000000-0000-0000-0000-000000000001"

    async def ctx(uid, db):
        return {"empresa": "Demo", "_documentos_abrir": {"E1": {"filename": "acta.pdf", "s3_key": "k"}}}

    def turno(mensajes, contexto, emit, leer, nombre):
        emit({"t": "texto", "d": "Déjame revisar. "})
        emit({"t": "leyendo", "doc": nombre("E1")})
        emit({"t": "texto", "d": "Se aprobaron 2.5 millones."})
        return {"reply": "Déjame revisar. Se aprobaron 2.5 millones.", "accion": None}

    monkeypatch.setattr(f"{R}.get_anchor_board_session_id", anchor)
    monkeypatch.setattr(f"{R}.build_contexto", ctx)
    monkeypatch.setattr("app.services.ai.todd_secretario.stream_todd_secretario_turn", turno)
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", lambda: _SesionFalsa(guardados))

    db = AsyncMock()
    res = MagicMock(); res.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=res)

    async def _db():
        yield db

    async def _uid():
        return "u1"

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user_id] = _uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/todd-secretario/mensajes/stream", json={"content": "¿Dividendos?"})
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    eventos = [json.loads(l) for l in r.text.splitlines() if l.strip()]
    assert [e["t"] for e in eventos] == ["texto", "leyendo", "texto", "fin"]
    assert eventos[1]["doc"] == "acta.pdf"
    assert [g.role for g in guardados] == ["user", "assistant"]
    assert guardados[1].content == "Déjame revisar. Se aprobaron 2.5 millones."


def test_sin_api_key_responde_con_un_evento_de_texto(monkeypatch):
    from app.services.ai import todd_secretario as ts
    monkeypatch.setattr(ts.settings, "ANTHROPIC_API_KEY", "")
    eventos = []
    r = ts.stream_todd_secretario_turn([{"role": "user", "content": "hola"}],
                                       {"tablero": {"total": 3, "por_estado": {}}}, eventos.append)
    assert eventos and eventos[0]["t"] == "texto" and r["reply"] == eventos[0]["d"]
