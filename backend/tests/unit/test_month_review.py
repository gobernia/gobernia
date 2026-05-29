from app.schemas.annual_plan import CloseMonthRequest, ApplyProposalRequest


def test_close_request_kpis_default_empty():
    r = CloseMonthRequest()
    assert r.kpis == {}
    r2 = CloseMonthRequest(kpis={"Razón corriente": 1.2})
    assert r2.kpis["Razón corriente"] == 1.2


def test_apply_proposal_request():
    a = ApplyProposalRequest(proposal_id="abc")
    assert a.proposal_id == "abc"
