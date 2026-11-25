/**
 * Avisos entre el tablero, la campanita y Todd (el botón flotante y su chat), con eventos de
 * ventana para que ninguna página tenga que conocer a las demás.
 *
 *   todd:abrir          abre el panel de Todd
 *   todd:cerrar         lo cierra
 *   todd:aviso          globo junto al botón de Todd ({ texto, leyendo? })
 *   todd:nuevo-mensaje  Todd dejó un mensaje en su chat (el chat y la campanita se recargan)
 *   todd:subir          el cliente quiere subir otro documento a una tarea ({ taskId })
 */

export interface ToddAviso {
  texto: string
  /** true mientras el Auditor lee el documento (el globo muestra que está trabajando). */
  leyendo?: boolean
}

const emitir = (nombre: string, detail?: unknown) =>
  window.dispatchEvent(detail === undefined ? new Event(nombre) : new CustomEvent(nombre, { detail }))

export const abrirTodd = () => emitir("todd:abrir")
export const cerrarTodd = () => emitir("todd:cerrar")
export const avisarTodd = (aviso: ToddAviso) => emitir("todd:aviso", aviso)
export const nuevoMensajeDeTodd = () => emitir("todd:nuevo-mensaje")
export const pedirSubirDocumento = (taskId: string) => emitir("todd:subir", { taskId })

/** Qué es lo que se subió (lo dice el Auditor) y si es otro documento, p. ej. un CV. */
export interface QueSeSubio {
  documento?: string
  otro_documento?: boolean
}

/** Lo que dice el globo cuando el Auditor termina de leer un documento recién subido. */
export function textoDelAviso(estado: string, tarea: string, subido?: QueSeSubio | null): string {
  return `Revisé tu documento de ${detalleDeRevision(estado, tarea, subido)}`
}

/** Lo que dice la campanita de una revisión de documento (el detalle está en el chat de Todd). */
export function detalleDeRevision(estado: string, tarea: string, subido?: QueSeSubio | null): string {
  if (subido?.otro_documento && estado !== "validada") {
    const es = subido.documento ? ` (es ${subido.documento})` : ""
    return `«${tarea}»: creo que te equivocaste de documento${es}. Te digo cuál necesito.`
  }
  switch (estado) {
    case "validada": return `«${tarea}»: queda validado para el Consejo.`
    case "parcial": return `«${tarea}»: es un avance parcial. Te digo qué falta.`
    case "insuficiente": return `«${tarea}»: todavía no alcanza. Te digo qué falta y qué más sirve.`
    default: return `«${tarea}»: no lo pude leer. Te digo qué hacer.`
  }
}
