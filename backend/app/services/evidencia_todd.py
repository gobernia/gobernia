"""Lo que Todd le dice al dueño en su chat cuando el Auditor termina de leer un documento recién
subido. Se arma con el veredicto del Auditor, sin otra llamada a la IA: llega al instante y no
cuesta más.

La idea (pedida por el dueño de Gobernia): no basta con decir "falta sustento"; el cliente sube lo
que tiene. Todd le dice qué sí está, qué falta y qué otra cosa también sirve, y lo invita a seguir
la conversación si no tiene ese documento.
"""


def mensaje_de_todd(veredicto: dict, tarea: str, archivo: str, subido_por: str | None = None) -> str:
    """`subido_por`: nombre del responsable si lo subió desde su enlace (el mensaje es para el dueño)."""
    estado = veredicto.get("estado")
    motivo = str(veredicto.get("motivo") or "").strip()
    cubre = str(veredicto.get("cubre") or "").strip()
    falta = str(veredicto.get("falta") or "").strip()
    alternativas = [str(a).strip() for a in (veredicto.get("alternativas") or []) if str(a).strip()]
    documento = str(veredicto.get("documento") or "").strip()
    quien = (subido_por or "").strip()
    otro = bool(veredicto.get("otro_documento")) and estado != "validada"

    # El PDF «Avance contado a Todd» ya dice qué es en su nombre: no se repite entre paréntesis.
    dice_que_es = documento and not otro and not archivo.startswith("Avance contado a Todd")
    nombre = f"«{archivo}»" + (f" ({documento})" if dice_que_es else "")
    inicio = (f"{quien} subió {nombre} para la tarea «{tarea}» y lo revisé." if quien
              else f"Revisé {nombre} para la tarea «{tarea}».")
    tambien_sirve = ("Si no tienes ese documento, también sirve:\n" + "\n".join(f"- {a}" for a in alternativas)
                     if alternativas else "")

    # Se subió otro documento (p. ej. un CV para una tarea de flujo de caja): se dice claro.
    if otro:
        sujeto = f"Creo que {quien} se equivocó" if quien else "Creo que te equivocaste"
        cierre = (f"Pídele a {quien} el documento correcto, o dime qué tienen y buscamos otra forma de demostrarlo."
                  if quien else
                  "Sube el documento correcto cuando lo tengas, o dime qué tienes y buscamos otra forma de demostrarlo.")
        partes = [inicio, f"{sujeto} de documento: esto es **{documento or 'otro documento'}**, "
                          "y no tiene que ver con lo que pide la tarea.",
                  f"**Para esta tarea necesito:** {falta or motivo}", tambien_sirve, cierre]
        return "\n\n".join(p for p in partes if p)

    if estado == "validada":
        return "\n\n".join(p for p in (inicio, cubre or motivo,
                                       "Queda **validado** para la sesión del Consejo.") if p)

    if estado in ("parcial", "insuficiente"):
        cierre = (f"Puedes subir otro documento o pedírselo a {quien}, o dime qué tienen y buscamos otra forma "
                  "de demostrarlo." if quien else
                  "Puedes subir otro documento, o dime qué tienes y buscamos otra forma de demostrarlo.")
        partes = [inicio, f"**Ya está:** {cubre}" if cubre else "", f"**Falta:** {falta or motivo}",
                  tambien_sirve, cierre]
        return "\n\n".join(p for p in partes if p)

    # sin_revisar: no se pudo leer o revisar.
    return (f"Intenté revisar «{archivo}»{f' (lo subió {quien})' if quien else ''} para la tarea «{tarea}», "
            "pero no pude leerlo. " + (f"{motivo} " if motivo else "")
            + "Si puedes, súbelo en PDF o en Excel (.xlsx).").strip()
