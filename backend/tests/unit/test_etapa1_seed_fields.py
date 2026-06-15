from app.schemas.etapa1 import Etapa1Input
from app.schemas.enums import IndustryType, YearsOperating, EmployeeRange, RevenueRange, BranchCount, BoardStatus
from app.services.ai.memory_buffer import build_etapa1_memory


def _base(**over):
    data = dict(
        company_name="ACME", industry=IndustryType.other, industry_custom="Software",
        location_city="CDMX", location_state="CDMX", location_country="México",
        years_operating=YearsOperating.startup, employees=EmployeeRange.small,
        annual_revenue=RevenueRange.one_to_5m, branches=BranchCount.single,
        is_family_business=False, has_board=BoardStatus.no,
    )
    data.update(over)
    return Etapa1Input(**data)


def test_website_and_competitors_optional_default():
    inp = _base()
    assert inp.website is None
    assert inp.competitors == []


def test_website_and_competitors_accepted():
    inp = _base(website="https://acme.com", competitors=["Globex", "Initech"])
    assert inp.website == "https://acme.com"
    assert inp.competitors == ["Globex", "Initech"]


def test_competitors_capped_and_trimmed():
    inp = _base(competitors=[" A ", "", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"])
    assert "" not in inp.competitors
    assert inp.competitors[0] == "A"
    assert len(inp.competitors) <= 10


def test_memory_buffer_includes_seed_fields():
    mb = build_etapa1_memory(_base(website="https://acme.com", competitors=["Globex"]), [])
    assert mb["company"]["website"] == "https://acme.com"
    assert mb["company"]["competitors"] == ["Globex"]
