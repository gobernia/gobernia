"""Motor determinista de cobertura (Bloque B2).
Distribuye los temas activos sobre las N sesiones: permanentes en todas; cobertura
escalonada por grupo de frecuencia; anuales ancladas al cierre del año."""
from app.models.board_theme import BoardTheme


def theme_sessions(
    themes: list[BoardTheme], total_sessions: int = 12,
) -> list[tuple[BoardTheme, list[int]]]:
    """Devuelve (tema, [sesiones]) para cada tema ACTIVO. Determinista, sin DB."""
    out: list[tuple[BoardTheme, list[int]]] = []
    cobertura_by_freq: dict[int, list[BoardTheme]] = {}

    for t in themes:
        if not t.active:
            continue
        if t.type == "permanente":
            out.append((t, list(range(1, total_sessions + 1))))
        elif t.type == "cobertura":
            cobertura_by_freq.setdefault(t.every_n_sessions, []).append(t)
        else:  # emergente
            out.append((t, []))

    for n, group in sorted(cobertura_by_freq.items()):
        group.sort(key=lambda x: x.order_index)
        for i, t in enumerate(group):
            if n == total_sessions:  # anual: anclar al cierre del año
                s = total_sessions - i
                out.append((t, [s] if s >= 1 else []))
            else:
                offset = i % n
                out.append((t, [s for s in range(1, total_sessions + 1) if (s - 1) % n == offset]))

    return out


def scheduled_for_session(
    themes: list[BoardTheme], month_index: int, total_sessions: int = 12,
) -> dict[str, list[BoardTheme]]:
    """Temas activos programados en una sesión, agrupados por tipo y ordenados."""
    permanente: list[BoardTheme] = []
    cobertura: list[BoardTheme] = []
    for t, sessions in theme_sessions(themes, total_sessions):
        if month_index in sessions:
            if t.type == "permanente":
                permanente.append(t)
            elif t.type == "cobertura":
                cobertura.append(t)
    permanente.sort(key=lambda x: x.order_index)
    cobertura.sort(key=lambda x: x.order_index)
    return {"permanente": permanente, "cobertura": cobertura}
