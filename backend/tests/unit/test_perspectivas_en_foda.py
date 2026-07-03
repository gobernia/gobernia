from app.services.ai.foda_into_plan import augment_buffer_with_foda


def test_augment_incluye_perspectivas_en_narrative():
    mb = {"ai_context": {"company_narrative": "Base."}}
    foda = {"fortalezas": ["x"], "debilidades": [], "oportunidades": [], "amenazas": [], "sintesis": "s"}
    persp = {"contradicciones": ["El dueño cree X, los clientes perciben Y"],
             "puntos_ciegos": ["Falta seguimiento a clientes"]}
    out = augment_buffer_with_foda(mb, foda, ["Crecer"], perspectivas=persp)
    narr = out["ai_context"]["company_narrative"]
    assert "clientes perciben Y" in narr
    assert "Falta seguimiento a clientes" in narr
