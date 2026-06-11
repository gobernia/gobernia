"""Completitud de datos de la empresa antes de gastar tokens (generar plan / crear sesión).

El onboarding puede completarse marcando KPIs como "no sé" (unknown=True), así que tener
las 8 etapas completas NO garantiza que existan datos. Este módulo valida que los datos
realmente estén: perfil con nombre y TODOS los KPIs configurados con valor real.
"""


def missing_company_data(memory_buffer: dict | None) -> list[str]:
    """Devuelve la lista de faltantes (vacía = datos completos)."""
    mb = memory_buffer or {}
    faltantes: list[str] = []

    if not (mb.get("company") or {}).get("name"):
        faltantes.append("el perfil de tu empresa (etapa 1)")

    kpis = mb.get("kpis") or {}
    total = 0
    sin_valor = 0
    for lst in kpis.values():
        for k in (lst or []):
            if not isinstance(k, dict):
                continue
            total += 1
            if k.get("unknown") or k.get("current_value") is None:
                sin_valor += 1
    if total == 0:
        faltantes.append("tus KPIs (etapa 5)")
    elif sin_valor:
        faltantes.append(f"{sin_valor} de {total} KPIs sin valor (etapa 5)")

    return faltantes
