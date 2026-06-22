from app.services.ai.foda_into_plan import augment_buffer_with_foda


def test_augment_inyecta_foda_y_metas_en_narrative():
    mb = {"company": {"name": "X"}, "ai_context": {"company_narrative": "Empresa X."}}
    foda = {"fortalezas": ["Buen equipo"], "debilidades": ["Márgenes bajos"],
            "oportunidades": ["Mercado online"], "amenazas": ["Aranceles"]}
    out = augment_buffer_with_foda(mb, foda, ["Quiero más clientes", "Quiero reducir costos"])
    narr = out["ai_context"]["company_narrative"]
    assert "Empresa X." in narr
    assert "Márgenes bajos" in narr
    assert "Quiero más clientes" in narr
    assert "Márgenes bajos" not in mb["ai_context"]["company_narrative"]


def test_augment_sin_foda_devuelve_buffer_equivalente():
    mb = {"company": {"name": "X"}}
    out = augment_buffer_with_foda(mb, None, [])
    assert out.get("company", {}).get("name") == "X"
