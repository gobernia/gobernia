from app.models import Base
from app.models.board_theme import BoardTheme


def test_board_themes_table_registered():
    table = Base.metadata.tables.get("board_themes")
    assert table is not None
    cols = set(table.columns.keys())
    assert {"id", "annual_plan_id", "key", "label", "type",
            "every_n_sessions", "active", "is_default", "order_index",
            "created_at", "updated_at"} <= cols


def test_board_theme_instantiable():
    t = BoardTheme(annual_plan_id=None, key="finanzas", label="Finanzas",
                   type="permanente", every_n_sessions=1)
    assert t.key == "finanzas"
    assert t.type == "permanente"
