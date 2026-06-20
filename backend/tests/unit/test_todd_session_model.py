from app.models.todd_session import ToddSession


def test_todd_session_construye_con_defaults_explicitos():
    s = ToddSession(user_id="u1", status="active", messages=[], state={})
    assert s.user_id == "u1"
    assert s.status == "active"
    assert s.messages == []
    assert s.state == {}


def test_todd_session_tablename():
    assert ToddSession.__tablename__ == "todd_sessions"
