from app.services.ai.todd import externo
from app.services.ai.todd.agent import enforce_coverage_against


def test_pestel_son_seis_categorias():
    assert externo.PESTEL_CATS == ["politicos", "economicos", "sociales", "tecnologicos", "ambiental", "legal"]
    assert all(externo.PESTEL_BANK.get(c) for c in externo.PESTEL_CATS)


def test_metas_base_tiene_siete():
    assert len(externo.METAS_BASE) == 7


def test_build_externo_prompt_incluye_pestel_y_diagnostico():
    p = externo.build_externo_prompt({"areas_cubiertas": []}, "DIAGNÓSTICO: márgenes apretados; competidor Wizeline.")
    assert "tecnológic" in p.lower() or "tecnologic" in p.lower()
    assert "Wizeline" in p
    assert "oportunidad" in p.lower() and "amenaza" in p.lower()
    assert "PESTEL" not in p


def test_enforce_coverage_against_bloquea_done_incompleto():
    turn = {"done": True, "state": {"areas_cubiertas": ["politicos"]}}
    out = enforce_coverage_against(turn, externo.PESTEL_CATS)
    assert out["done"] is False


def test_enforce_coverage_against_permite_done_completo():
    turn = {"done": True, "state": {"areas_cubiertas": externo.PESTEL_CATS}}
    assert enforce_coverage_against(turn, externo.PESTEL_CATS)["done"] is True
