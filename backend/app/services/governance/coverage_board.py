"""Cálculo del Tablero de Cobertura (Bloque B4). Determinista, sin DB."""
from app.models.board_theme import BoardTheme
from app.services.governance.coverage_calendar import theme_sessions


def coverage_status(theme_type: str, deficit: int) -> str:
    if deficit <= 0:
        return "en_tiempo"
    if theme_type == "permanente":  # escala más rápido (cada sesión cuentan)
        return "atrasado" if deficit == 1 else "critico"
    if deficit == 1:
        return "riesgo"
    if deficit == 2:
        return "atrasado"
    return "critico"


def coverage_rows(themes: list[BoardTheme], months, active_index: int, total_sessions: int = 12) -> list[dict]:
    """`months` = objetos con atributo `covered_themes` (lista de keys o None)."""
    covered_by_key: dict[str, int] = {}
    for m in months:
        for k in (m.covered_themes or []):
            covered_by_key[k] = covered_by_key.get(k, 0) + 1

    rows: list[dict] = []
    for t, sessions in theme_sessions(themes, total_sessions):
        if t.type not in ("permanente", "cobertura"):
            continue
        esperadas = sum(1 for s in sessions if s <= active_index)
        realizadas = covered_by_key.get(t.key, 0)
        rows.append({
            "key": t.key, "label": t.label, "type": t.type,
            "frecuencia_anual": len(sessions),
            "esperadas": esperadas, "realizadas": realizadas,
            "estado": coverage_status(t.type, esperadas - realizadas),
        })
    return rows
