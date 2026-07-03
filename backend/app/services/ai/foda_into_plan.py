"""Inyecta el FODA + metas priorizadas en el memory_buffer (vía company_narrative) para que el
generador de plan a 3 años (que ya lee company_narrative) alinee objetivos/tareas a lo prioritario."""
import copy


def augment_buffer_with_foda(memory_buffer: dict, foda: dict | None, metas_orden: list,
                              perspectivas: dict | None = None) -> dict:
    mb = copy.deepcopy(memory_buffer or {})
    if not foda and not metas_orden and not perspectivas:
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

    persp = perspectivas or {}
    persp_lineas = []
    for etiqueta, clave in (("Contradicciones", "contradicciones"),
                            ("Puntos ciegos", "puntos_ciegos"),
                            ("Coincidencias", "coincidencias")):
        items = [str(x) for x in (persp.get(clave) or []) if str(x).strip()]
        if items:
            persp_lineas.append(f"{etiqueta}: " + "; ".join(items))
    bloque_persp = ("\n\nPERSPECTIVAS DE OTRAS VOCES (empleados, clientes, directivos):\n"
                    + "\n".join(persp_lineas)) if persp_lineas else ""

    if not partes and not bloque_persp:
        return mb
    ai = dict(mb.get("ai_context") or {})
    prev = str(ai.get("company_narrative") or "").strip()
    bloque = ("ANÁLISIS FODA Y PRIORIDADES:\n" + "\n".join(partes)) if partes else ""
    nuevo = (bloque + bloque_persp).strip()
    ai["company_narrative"] = (prev + "\n\n" + nuevo) if prev else nuevo
    mb["ai_context"] = ai
    return mb
