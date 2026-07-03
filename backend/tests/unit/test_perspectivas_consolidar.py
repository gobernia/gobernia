from app.services.ai.perspectivas.consolidar import _fallback, consolidar_perspectivas


def test_fallback_agrega_por_rol_y_conteo():
    invites = [
        {"role": "empleado", "name": "Juan", "state": {"percepciones": ["faltan procesos"]},
         "messages": [{"role": "user", "text": "Faltan procesos claros"}]},
        {"role": "cliente", "name": None, "state": {},
         "messages": [{"role": "user", "text": "Buen servicio pero lento"}]},
    ]
    out = _fallback(invites)
    assert out["conteo"]["empleado"] == 1 and out["conteo"]["cliente"] == 1
    assert "empleado" in out["por_rol"] and "cliente" in out["por_rol"]
    # roles anónimos NO exponen el nombre
    assert "Juan" not in str(out)


def test_consolidar_sin_api_key_usa_fallback(monkeypatch):
    monkeypatch.setattr("app.services.ai.perspectivas.consolidar.settings.ANTHROPIC_API_KEY", "")
    out = consolidar_perspectivas({}, [{"role": "cliente", "name": None, "state": {},
                                        "messages": [{"role": "user", "text": "ok"}]}])
    assert set(out.keys()) >= {"coincidencias", "contradicciones", "puntos_ciegos", "por_rol", "conteo"}
