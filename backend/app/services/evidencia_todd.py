"""Lo que Todd le dice al dueño en su chat cuando el Auditor termina de leer un documento recién
subido. Se arma con el veredicto del Auditor, sin otra llamada a la IA: llega al instante y no
cuesta más.

La idea (pedida por el dueño de Gobernia): no basta con decir "falta sustento"; el cliente sube lo
que tiene. Todd le dice qué sí está, qué falta y qué otra cosa también sirve, y lo invita a seguir
la conversación si no tiene ese documento.
"""


def mensaje_de_todd(veredicto: dict, tarea: str, archivo: str) -> str:
    estado = veredicto.get("estado")
    motivo = str(veredicto.get("motivo") or "").strip()
    cubre = str(veredicto.get("cubre") or "").strip()
    falta = str(veredicto.get("falta") or "").strip()
    alternativas = [str(a).strip() for a in (veredicto.get("alternativas") or []) if str(a).strip()]
    documento = str(veredicto.get("documento") or "").strip()
    inicio = f"Revisé «{archivo}» para la tarea «{tarea}»."

    # Se subió otro documento (p. ej. un CV para una tarea de flujo de caja): se dice claro.
    if veredicto.get("otro_documento") and estado != "validada":
        partes = [inicio, f"Creo que te equivocaste de documento: esto es **{documento or 'otro documento'}**, "
                          "y no tiene que ver con lo que pide la tarea."]
        partes.append(f"**Para esta tarea necesito:** {falta or motivo}")
        if alternativas:
            partes.append("Si no tienes ese documento, también sirve:\n" + "\n".join(f"- {a}" for a in alternativas))
        partes.append("Sube el documento correcto cuando lo tengas, o dime qué tienes y buscamos otra forma de demostrarlo.")
        return "\n\n".join(partes)

    if documento:
        inicio = f"Revisé «{archivo}» ({documento}) para la tarea «{tarea}»."

    if estado == "validada":
        return "\n\n".join(p for p in (inicio, cubre or motivo,
                                       "Queda **validado** para la sesión del Consejo.") if p)

    if estado in ("parcial", "insuficiente"):
        partes = [inicio]
        if cubre:
            partes.append(f"**Ya está:** {cubre}")
        partes.append(f"**Falta:** {falta or motivo}")
        if alternativas:
            partes.append("Si no tienes ese documento, también sirve:\n"
                          + "\n".join(f"- {a}" for a in alternativas))
        partes.append("Puedes subir otro documento, o dime qué tienes y buscamos otra forma de demostrarlo.")
        return "\n\n".join(partes)

    # sin_revisar: no se pudo leer o revisar.
    return (f"Intenté revisar «{archivo}» para la tarea «{tarea}», pero no pude leerlo. "
            + (f"{motivo} " if motivo else "")
            + "Si puedes, súbelo en PDF o en Excel (.xlsx).").strip()
