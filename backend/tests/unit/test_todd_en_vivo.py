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
    """Imita client.messages.stream: entrega el JSON en trozos; la primera vez puede fallar.
    Con `json`/`final` entrega otro JSON y otro mensaje final (p. ej. uno cortado)."""

    def __init__(self, fallar_una_vez=False, json=TURNO_JSON, final="mensaje-final", roto=False):
        self.fallar = fallar_una_vez
        self.json, self.final, self.roto = json, final, roto
        self.kwargs = []
        self.messages = SimpleNamespace(stream=self._stream)

    @contextmanager
    def _stream(self, **kwargs):
        self.kwargs.append(kwargs)
        if self.fallar:
            self.fallar = False
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
        trozos = [self.json[i:i + 7] for i in range(0, len(self.json), 7)]
        eventos = [SimpleNamespace(type="message_start")] + [_evento(t) for t in trozos]
        yield _Stream(eventos, self.final, self.roto)


class _Stream:
    def __init__(self, eventos, final="mensaje-final", roto=False):
        self.eventos, self.final, self.roto = eventos, final, roto

    def __iter__(self):
        for i, ev in enumerate(self.eventos):
            if self.roto and i == len(self.eventos) // 2:
                # Así falla la librería cuando el JSON en vivo viene mal formado.
                raise ValueError("expected ident at line 1 column 30")
            yield ev

    def get_final_message(self):
        return self.final


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


def test_si_el_json_en_vivo_llega_mal_formado_se_repite_por_la_via_normal(monkeypatch):
    normal = []
    monkeypatch.setattr(en_vivo, "_create_with_retry", lambda client, **kw: normal.append(kw) or "turno-normal")
    cliente = _Cliente(roto=True)
    tools = [{"name": "responder_turno"}]
    assert stream_turno(cliente, lambda c: None, model="m", tools=tools, messages=[]) == "turno-normal"
    # La vía normal es la de siempre: sin el modo en vivo.
    assert normal == [{"model": "m", "tools": [{"name": "responder_turno"}], "messages": []}]
    assert tools == [{"name": "responder_turno"}]


# ── Blindajes: el modo en vivo no corrige tipos ni avisa si el expediente se cortó ────────

from app.services.ai.todd import agent  # noqa: E402
from app.services.ai.todd.agent import _entrada_del_turno, _normalize_turn  # noqa: E402


def test_done_y_expects_detail_solo_son_si_cuando_la_ia_dice_que_si():
    assert _normalize_turn({"done": "false"})["done"] is False
    assert _normalize_turn({"done": "False "})["done"] is False
    assert _normalize_turn({"done": "true"})["done"] is True
    assert _normalize_turn({"done": True})["done"] is True
    assert _normalize_turn({"done": False})["done"] is False and _normalize_turn({})["done"] is False
    assert _normalize_turn({"expects_detail": "false", "input": "text"})["expects_detail"] is False
    assert _normalize_turn({"expects_detail": True, "input": "text"})["expects_detail"] is True


def _respuesta(stop_reason, entrada):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="tool_use", input=entrada)])


def test_turno_cortado_no_trae_expediente_ni_cierra():
    cortado = _entrada_del_turno(_respuesta("max_tokens", {"message": "¿Y?", "state": {"company": {}}, "done": True}))
    assert "state" not in cortado and cortado["done"] is False and cortado["message"] == "¿Y?"
    # Un turno normal pasa tal cual.
    completo = {"message": "¿Y?", "state": {"company": {"name": "Keting"}}, "done": False}
    assert _entrada_del_turno(_respuesta("tool_use", dict(completo))) == completo


@pytest.mark.asyncio
async def test_si_la_respuesta_se_corta_se_conserva_el_expediente_completo(monkeypatch):
    """De punta a punta con la función real de Todd: la IA se queda sin espacio a la mitad del
    expediente. Se guarda la conversación y el expediente anterior queda intacto."""
    from jiter import from_json
    previo = {"company": {"name": "Keting Media", "employees": 40}, "areas_cubiertas": ["rh"]}
    parcial = TURNO_JSON[:TURNO_JSON.index('"Keting"') + 4]  # ...'"company": {"name": "Ke'
    cliente = _Cliente(json=parcial, final=_respuesta("max_tokens", from_json(parcial.encode(), partial_mode=True)))
    assert cliente.final.content[0].input["state"] == {"company": {}}  # lo que habría pisado al bueno
    monkeypatch.setattr(agent.settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(agent.anthropic, "Anthropic", lambda api_key: cliente)

    db, fabrica = _db_falsa()
    sess = ToddSession(user_id="u1", status="active", phase="interno",
                       messages=[{"role": "todd", "text": "¿Nombre?", "options": None}], state=dict(previo))
    monkeypatch.setattr("app.api.v1.todd.router.AsyncSessionLocal", fabrica)
    monkeypatch.setattr("app.api.v1.todd.router._current", AsyncMock(return_value=sess))

    eventos = _eventos(await _llamar_stream("/onboarding/todd/turn/stream", {"answer": "Keting"}))
    assert eventos[-1][0] == "fin" and eventos[-1][1]["done"] is False
    assert eventos[-1][1]["areas_cubiertas"] == ["rh"]  # la barra de avance no se reinicia
    assert sess.state == previo
    assert [m["text"] for m in sess.messages] == ["¿Nombre?", "Keting", '¿Cuántas personas "clave" tienes? 🙂']
    db.commit.assert_awaited_once()


def test_la_via_normal_tambien_conserva_el_expediente_si_se_corta(monkeypatch):
    monkeypatch.setattr(agent.settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(agent.anthropic, "Anthropic", lambda api_key: None)
    monkeypatch.setattr(agent, "_create_with_retry", lambda client, **kw: _respuesta(
        "max_tokens", {"message": "¿Y?", "state": {"company": {}}, "done": True}))
    turno = agent.run_todd_turn([{"role": "user", "text": "hola"}], {"company": {"name": "Keting"}})
    assert turno["state"] == {} and turno["done"] is False  # el router conserva el anterior


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
