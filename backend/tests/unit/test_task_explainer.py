from app.services.ai.task_explainer import parse_explicacion


def test_parse_explicacion_normaliza():
    d = parse_explicacion({"tiempo": "~2 h", "dificultad": "Fácil",
                           "que_es": "Definir el cliente ideal",
                           "como": ["Lista tus mejores clientes", "Busca qué tienen en común"]})
    assert d["tiempo"] == "~2 h"
    assert d["dificultad"] == "Fácil"
    assert d["que_es"].startswith("Definir")
    assert d["como"] == ["Lista tus mejores clientes", "Busca qué tienen en común"]


def test_parse_explicacion_defaults_seguros():
    d = parse_explicacion({})
    assert d["tiempo"] and d["dificultad"] in ("Fácil", "Media", "Difícil")
    assert isinstance(d["que_es"], str)
    assert isinstance(d["como"], list)


def test_parse_explicacion_dificultad_invalida_cae_a_media():
    d = parse_explicacion({"dificultad": "imposible"})
    assert d["dificultad"] == "Media"
