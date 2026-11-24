"""Todd puede decir de dónde salió un dato (caso real: la brecha 4.7% vs 14% venía de la
entrevista y Todd, sin verla, "confesó" haberla inventado)."""
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.ai import todd_secretario as ts
from app.services.ai.expediente import buscar, hojas


def _f(donde, dia, texto, ruta=""):
    return {"donde": donde, "fecha": datetime(2026, 11, dia, tzinfo=timezone.utc), "ruta": ruta, "texto": texto}


FUENTES = [
    _f("Plan: postura del Consejo", 24, "La diferencia entre el 4.7% reportado y el 14% de la Planeación Estratégica "
       "es una brecha de rentabilidad que hay que conciliar."),
    _f("Entrevista con Todd (entrevista) — lo que respondió el dueño", 11,
       "En la planeación estratégica salía un margen de 14 %, pero contabilidad reporta 4,7%."),
    _f("Diagnóstico estratégico", 11, "Ventas 2014: crecieron 140% en una década; margen bruto 14.5%."),
    _f("Datos de la empresa", 11, "Brecha de Rentabilidad no conciliada", ruta="hallazgos › financiero"),
]


def test_encuentra_la_cifra_y_dice_primero_donde_nacio():
    r = buscar(FUENTES, "14%")
    lineas = r.splitlines()
    assert "aparece en 2 lugar(es)" in lineas[0]
    assert lineas[1].startswith("1. Entrevista con Todd (entrevista) — lo que respondió el dueño (11/11/2026)")
    assert "margen de 14 %" in lineas[1]
    assert lineas[2].startswith("2. Plan: postura del Consejo (24/11/2026)")
    # 140%, 2014 y 14.5% no son "14%".
    assert "Diagnóstico" not in r


def test_cifras_con_coma_o_punto_y_frases_sin_acentos():
    assert "aparece en 2 lugar(es)" in buscar(FUENTES, "4.7%")
    r = buscar(FUENTES, "brecha de rentabilidad")
    assert "Datos de la empresa › hallazgos › financiero" in r and "Plan: postura del Consejo" in r


def test_si_no_esta_lo_dice_sin_inventar():
    r = buscar(FUENTES, "-23%")
    assert r.startswith("No encontré «-23%» en el expediente")
    assert buscar(FUENTES, "de la").startswith("Dame una cifra")


def test_hojas_usa_nombres_legibles_en_la_ruta():
    roadmap = {"pilares": [{"nombre": "Rentabilidad", "kpis": [{"kpi": "Margen neto", "meta": "14%"}]}]}
    assert list(hojas(roadmap)) == [("pilares › Rentabilidad", "Rentabilidad"),
                                    ("pilares › Rentabilidad › Margen neto", "Margen neto"),
                                    ("pilares › Rentabilidad › Margen neto", "14%")]


def test_reglas_nuevas_en_el_prompt():
    p = ts.build_system_prompt({"tablero": {"total": 0, "por_estado": {}}})
    assert "ni CIFRAS" in p and "buscar_en_expediente" in p
    assert "NUNCA digas que inventaste algo que no escribiste TÚ" in p


class _ClienteFalso:
    """Ronda 1: Todd pide buscar «14%». Ronda 2: responde con lo encontrado."""

    def __init__(self):
        self.llamadas = []
        self.messages = SimpleNamespace(stream=self._stream)

    @contextmanager
    def _stream(self, **kw):
        self.llamadas.append(kw)
        if len(self.llamadas) == 1:
            bloque = SimpleNamespace(type="tool_use", id="tu1", name="buscar_en_expediente",
                                     input={"consulta": "14%"},
                                     model_dump=lambda: {"type": "tool_use", "id": "tu1",
                                                         "name": "buscar_en_expediente", "input": {"consulta": "14%"}})
            yield SimpleNamespace(text_stream=iter([]), get_final_message=lambda: SimpleNamespace(content=[bloque]))
        else:
            texto = "Sale de tu entrevista del 11 de noviembre."
            yield SimpleNamespace(text_stream=iter([texto]), get_final_message=lambda: SimpleNamespace(
                content=[SimpleNamespace(type="text", text=texto)]))


def test_todd_busca_en_el_expediente_antes_de_responder(monkeypatch):
    cliente = _ClienteFalso()
    monkeypatch.setattr(ts.settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(ts.anthropic, "Anthropic", lambda **kw: cliente)
    eventos, consultas = [], []

    def buscar_expediente(q):
        consultas.append(q)
        return buscar(FUENTES, q)

    r = ts.stream_todd_secretario_turn([{"role": "user", "content": "¿De dónde sacaste el 14%?"}],
                                       {"tablero": {"total": 0, "por_estado": {}}}, eventos.append,
                                       buscar_expediente=buscar_expediente)
    assert consultas == ["14%"]
    assert {"t": "leyendo", "doc": "tu expediente"} in eventos
    assert "buscar_en_expediente" in [t["name"] for t in cliente.llamadas[0]["tools"]]
    resultado = cliente.llamadas[1]["messages"][-1]["content"][0]
    assert resultado["type"] == "tool_result" and "lo que respondió el dueño" in resultado["content"][0]["text"]
    assert r["reply"] == "Sale de tu entrevista del 11 de noviembre."
