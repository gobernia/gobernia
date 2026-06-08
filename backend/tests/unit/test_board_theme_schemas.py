import pytest
from pydantic import ValidationError

from app.schemas.board_theme import BoardThemeCreate, BoardThemeUpdate


def test_permanente_forces_freq_1():
    m = BoardThemeCreate(label="X", type="permanente", every_n_sessions=6)
    assert m.every_n_sessions == 1


def test_emergente_forces_null():
    m = BoardThemeCreate(label="X", type="emergente", every_n_sessions=3)
    assert m.every_n_sessions is None


def test_cobertura_rejects_bad_freq():
    with pytest.raises(ValidationError):
        BoardThemeCreate(label="X", type="cobertura", every_n_sessions=5)


def test_cobertura_accepts_valid_freq():
    m = BoardThemeCreate(label="X", type="cobertura", every_n_sessions=3)
    assert m.every_n_sessions == 3


def test_update_rejects_bad_freq():
    with pytest.raises(ValidationError):
        BoardThemeUpdate(every_n_sessions=7)
