from app.models.perspectiva_invite import PerspectivaInvite


def test_perspectiva_invite_tablename_y_columnas():
    assert PerspectivaInvite.__tablename__ == "perspectiva_invites"
    cols = PerspectivaInvite.__table__.columns
    for c in ("owner_user_id", "role", "invitee_name", "token", "status", "messages", "state"):
        assert c in cols, f"falta columna {c}"
    assert cols["token"].unique is True
    assert cols["status"].default.arg == "pending"


def test_perspectiva_invite_esta_registrado_en_metadata():
    from app.models import Base
    assert "perspectiva_invites" in Base.metadata.tables
