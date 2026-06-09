from app.schemas.orden_del_dia import ThemeRef
from app.schemas.annual_plan import ObjectiveOut
from app.services.pdf.orden_del_dia_pdf import build_orden_pdf


def _data():
    return {
        "month_index": 1,
        "period_label": "Enero 2026",
        "permanent_themes": [ThemeRef(key="fin", label="Resultados financieros", every_n_sessions=1)],
        "coverage_themes": [ThemeRef(key="aud", label="Auditoría", every_n_sessions=3)],
        "covered_keys": ["fin"],
        "objectives": [ObjectiveOut(id="o1", title="Mejorar margen", kpi_refs=["EBITDA"])],
    }


def test_build_orden_pdf_returns_pdf_bytes():
    pdf = build_orden_pdf(_data(), "Acme S.A.")
    assert isinstance(pdf, (bytes, bytearray))
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500


def test_build_orden_pdf_without_company():
    pdf = build_orden_pdf(_data(), None)
    assert pdf[:4] == b"%PDF"


def test_build_orden_pdf_escapes_ampersand_in_title():
    data = _data()
    data["objectives"] = [ObjectiveOut(id="o1", title="Ventas & Marketing", kpi_refs=[])]
    pdf = build_orden_pdf(data, "Tom & Co")  # debe NO romper el parser XML de reportlab
    assert pdf[:4] == b"%PDF"
