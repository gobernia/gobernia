"""Inyecta el FODA + metas priorizadas en el memory_buffer (vía company_narrative) para que el
generador de plan a 3 años (que ya lee company_narrative) alinee objetivos/tareas a lo prioritario."""
import copy


def augment_buffer_with_foda(memory_buffer: dict, foda: dict | None, metas_orden: list) -> dict:
    mb = copy.deepcopy(memory_buffer or {})
    if not foda and not metas_orden:
        return mb
    partes = []
    if foda:
        for k, label in (("fortalezas", "Fortalezas"), ("debilidades", "Debilidades"),
                         ("oportunidades", "Oportunidades"), ("amenazas", "Amenazas")):
            items = [str(x) for x in (foda.get(k) or []) if str(x).strip()]
            if items:
                partes.append(f"{label}: " + "; ".join(items) + ".")
    if metas_orden:
        metas = [str(m) for m in metas_orden if str(m).strip()]
        if metas:
            partes.append("Prioridades del dueño (en orden): " + " > ".join(metas) + ".")
    if not partes:
        return mb
    ai = dict(mb.get("ai_context") or {})
    prev = str(ai.get("company_narrative") or "").strip()
    bloque = "ANÁLISIS FODA Y PRIORIDADES:\n" + "\n".join(partes)
    ai["company_narrative"] = (prev + "\n\n" + bloque) if prev else bloque
    mb["ai_context"] = ai
    return mb
