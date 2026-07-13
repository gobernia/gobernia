from app.models.annual_plan import AnnualPlan


def test_annual_plan_tiene_ciclo_de_validacion_del_roadmap():
    cols = AnnualPlan.__table__.columns
    assert "roadmap_status" in cols
    assert cols["roadmap_status"].default.arg == "borrador"
    assert cols["roadmap_status"].nullable is False
    assert "roadmap_validated_at" in cols
    assert cols["roadmap_validated_at"].nullable is True
