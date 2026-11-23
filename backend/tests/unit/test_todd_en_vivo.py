"""Turnos de Todd en vivo: la pregunta se manda mientras la IA escribe el expediente, y el turno
que se guarda es el mismo que sin streaming."""
from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user
from app.main import app
from app.models.todd_session import ToddSession
from app.services.ai.todd import streaming as en_vivo
from app.services.ai.todd.streaming import campos_visibles, stream_turno, texto_parcial

TURNO_JSON = ('{"message": "¿Cuántas personas \\"clave\\" tienes? \\ud83d\\ude42", "options": ["1-10", "11-50"], '
              '"input": "single_choice", "state": {"company": {"name": "Keting"}, "areas_cubiertas": ["rh"]}, '
              '"done": false}')


def test_texto_parcial_decodifica_lo_que_ya_llego():
    assert texto_parcial('{"message": "Hola') == "Hola"
    assert texto_parcial('{"message": "Dime \\"algo\\"\\nya') == 'Dime "algo"\nya'
    assert texto_parcial('{"message": "\\u00bfC\\u00f3mo') == "¿Cómo"
    # Un escape a medias no se muestra hasta completarse.
    assert texto_parcial('{"message": "ma\\u00') == "ma"
    assert texto_parcial('{"message": "ok \\ud83d') == "ok "
    assert texto_parcial('{"message": "ok \\ud83d\\ude42 fin"') == "ok 🙂 fin"
    assert texto_parcial('{"mess') == "" and texto_parcial("") == ""


def test_campos_visibles_esperan_a_que_opciones_e_input_esten_completos():
    assert campos_visibles('{"message": "¿Qué?", "options": ["A", "B') == {"message": "¿Qué?"}
    assert campos_visibles('{"message": "¿Qué?", "options": ["A", "B"], "input": "single_choice"') == {
        "message": "¿Qué?", "options": ["A", "B"], "input": "single_choice"}
    assert campos_visibles('{"message": "Cuéntame", "options": [], "input": "text", "state": {') == {
        "message": "Cuéntame", "options": None, "input": "text"}


def _evento(trozo: str):
    return SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="input_json_delta", partial_json=trozo))


class _Cliente:
    """Imita client.messages.stream: entrega el JSON en trozos; la primera vez puede fallar."""

    def __init__(self, fallar_una_vez=False):
        self.fallar = fallar_una_vez
        self.kwargs = []
        self.messages = SimpleNamespace(stream=self._stream)

    @contextmanager
    def _stream(self, **kwargs):
        self.kwargs.append(kwargs)
        if self.fallar:
            self.fallar = False
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
        trozos = [TURNO_JSON[i:i + 7] for i in range(0, len(TURNO_JSON), 7)]
        eventos = [SimpleNamespace(type="message_start")] + [_evento(t) for t in trozos]
        yield _Stream(eventos)


class _Stream:
    def __init__(self, eventos):
        self.eventos = eventos

    def __iter__(self):
        return iter(self.eventos)

    def get_final_message(self):
        return "mensaje-final"


def test_stream_turno_avisa_la_pregunta_y_devuelve_el_mensaje_final(monkeypatch):
    monkeypatch.setattr(en_vivo.time, "sleep", lambda s: None)
    avisos = []
    cliente = _Cliente(fallar_una_vez=True)
    final = stream_turno(cliente, avisos.append, model="m", tools=[{"name": "responder_turno"}], messages=[])
    assert final == "mensaje-final"
    # Reintentó tras el error de conexión, y pidió la entrada de la herramienta en vivo.
    assert len(cliente.kwargs) == 2 and cliente.kwargs[1]["tools"][0]["eager_input_streaming"] is True
    mensajes = [a["message"] for a in avisos]
    assert mensajes == sorted(mensajes, key=len) and mensajes[-1] == '¿Cuántas personas "clave" tienes? 🙂'
    assert avisos[-1] == {"message": '¿Cuántas personas "clave" tienes? 🙂', "options": ["1-10", "11-50"],
                          "input": "single_choice"}
    # El expediente no se manda al navegador.
    assert all("state" not in a for a in avisos)


# ── El endpoint ──────────────────────────────────────────────────────────────────────────


def _db_falsa():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    @asynccontextmanager
    async def fabrica():
        yield db
    return db, fabrica


async def _llamar_stream(path: str, body: dict) -> str:
    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1", "email": "a@b.com"}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/v1{path}", json=body)
            assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
            return r.text
    finally:
        app.dependency_overrides.clear()


def _eventos(texto: str) -> list[tuple[str, dict]]:
    import json
    out = []
    for bloque in texto.strip().split("\n\n"):
        lineas = dict(l.split(": ", 1) for l in bloque.splitlines() if not l.startswith(":"))
        if lineas:
            out.append((lineas["event"], json.loads(lineas["data"])))
    return out


@pytest.mark.asyncio
async def test_turno_en_vivo_manda_la_pregunta_y_guarda_lo_mismo_que_siempre(monkeypatch):
    db, fabrica = _db_falsa()
    sess = ToddSession(user_id="u1", status="active", phase="interno",
                       messages=[{"role": "todd", "text": "¿Nombre?", "options": None}], state={"company": {}})
    monkeypatch.setattr("app.api.v1.todd.router.AsyncSessionLocal", fabrica)
    monkeypatch.setattr("app.api.v1.todd.router._current", AsyncMock(return_value=sess))

    def turno(messages, state, avisar):
        assert messages[-1] == {"role": "user", "text": "Keting", "options": None} and state == {"company": {}}
        avisar({"message": "¿Cuán"})
        avisar({"message": "¿Cuántos son?", "options": None, "input": "text"})
        return {"message": "¿Cuántos son?", "options": None, "input": "text", "done": False,
                "state": {"company": {"name": "Keting"}, "areas_cubiertas": ["rh"]}, "expects_detail": False}
    monkeypatch.setattr("app.api.v1.todd.router.run_todd_turn", turno)

    eventos = _eventos(await _llamar_stream("/onboarding/todd/turn/stream", {"answer": "Keting"}))
    assert [e for e, _ in eventos] == ["pregunta", "pregunta", "fin"]
    assert eventos[-1][1] == {"message": "¿Cuántos son?", "options": None, "input": "text", "done": False,
                              "areas_cubiertas": ["rh"], "expects_detail": False}
    # Se guardó igual que en /turn: la respuesta, la pregunta nueva y el expediente completo.
    assert [m["text"] for m in sess.messages] == ["¿Nombre?", "Keting", "¿Cuántos son?"]
    assert sess.state == {"company": {"name": "Keting"}, "areas_cubiertas": ["rh"]}
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_si_la_ia_falla_no_se_guarda_nada(monkeypatch):
    db, fabrica = _db_falsa()
    sess = ToddSession(user_id="u1", status="active", phase="externo", messages=[], state={"x": 1})
    monkeypatch.setattr("app.api.v1.todd.router.AsyncSessionLocal", fabrica)
    monkeypatch.setattr("app.api.v1.todd.router._current", AsyncMock(return_value=sess))
    monkeypatch.setattr("app.api.v1.todd.router._diagnostico_ctx", AsyncMock(return_value="ctx"))

    def falla(messages, state, ctx, avisar):
        avisar({"message": "Hol"})
        raise RuntimeError("se cayó la IA")
    monkeypatch.setattr("app.api.v1.todd.router.run_externo_turn", falla)

    eventos = _eventos(await _llamar_stream("/onboarding/todd/externo/turn/stream", {"answer": "algo"}))
    assert [e for e, _ in eventos] == ["pregunta", "error"]
    assert sess.messages == [] and sess.state == {"x": 1}
    db.commit.assert_not_awaited()
