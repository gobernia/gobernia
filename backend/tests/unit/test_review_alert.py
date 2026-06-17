from types import SimpleNamespace
from app.services.governance.alerts import review_alert


def _month(idx, status, review=None):
    return SimpleNamespace(month_index=idx, status=status, review=review)


def test_alerta_cuando_hay_revision_con_propuestas_pendientes():
    months = [
        _month(1, "done", {"proposals": [{"applied": True}, {"applied": False}, {"applied": False}]}),
        _month(2, "active", None),
    ]
    a = review_alert(months)
    assert a is not None
    assert a["level"] == "info" and a["category"] == "revision"
    assert "2 propuesta" in a["message"]


def test_sin_alerta_si_todas_aplicadas():
    months = [_month(1, "done", {"proposals": [{"applied": True}]})]
    assert review_alert(months) is None


def test_sin_alerta_si_no_hay_mes_done():
    months = [_month(1, "active", None)]
    assert review_alert(months) is None
