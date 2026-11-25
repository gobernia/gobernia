/**
 * Avisos entre el tablero, la campanita y Todd (el botón flotante y su chat), con eventos de
 * ventana para que ninguna página tenga que conocer a las demás.
 *
 *   todd:abrir          abre el panel de Todd
 *   todd:cerrar         lo cierra
 *   todd:nuevo-mensaje  Todd dejó un mensaje en su chat (el chat y la campanita se recargan)
 *   todd:subir          el cliente quiere subir otro documento a una tarea ({ taskId })
 */

const emitir = (nombre: string, detail?: unknown) =>
  window.dispatchEvent(detail === undefined ? new Event(nombre) : new CustomEvent(nombre, { detail }))

export const abrirTodd = () => emitir("todd:abrir")
export const cerrarTodd = () => emitir("todd:cerrar")
export const nuevoMensajeDeTodd = () => emitir("todd:nuevo-mensaje")
export const pedirSubirDocumento = (taskId: string) => emitir("todd:subir", { taskId })

/** Lo que dice la campanita de una revisión de documento (el detalle está en el chat de Todd). */
export function detalleDeRevision(estado: string, tarea: string): string {
  switch (estado) {
    case "validada": return `«${tarea}»: queda validado para el Consejo.`
    case "parcial": return `«${tarea}»: es un avance parcial. Te digo qué falta.`
    case "insuficiente": return `«${tarea}»: todavía no alcanza. Te digo qué falta y qué más sirve.`
    default: return `«${tarea}»: no lo pude leer. Te digo qué hacer.`
  }
}
