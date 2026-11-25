/**
 * Avisos entre el tablero y Todd (el botón flotante y su chat), con eventos de ventana para que
 * ninguna página tenga que conocer a las demás.
 *
 *   todd:abrir          abre el panel de Todd
 *   todd:cerrar         lo cierra
 *   todd:aviso          globo junto al botón de Todd ({ texto, leyendo? })
 *   todd:nuevo-mensaje  Todd dejó un mensaje en su chat (el chat abierto se recarga)
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

/** Lo que dice el globo cuando el Auditor termina de leer un documento recién subido. */
export function textoDelAviso(estado: string, tarea: string): string {
  switch (estado) {
    case "validada": return `Revisé tu documento de «${tarea}»: queda validado.`
    case "parcial": return `Revisé tu documento de «${tarea}»: es un avance parcial. Te digo qué falta.`
    case "insuficiente": return `Revisé tu documento de «${tarea}»: todavía no alcanza. Te digo qué falta y qué más sirve.`
    default: return `No pude leer tu documento de «${tarea}». Te digo qué hacer.`
  }
}
