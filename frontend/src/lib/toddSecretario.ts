import api from "@/lib/api"

/**
 * Todd, el secretario del Consejo — chat permanente en el Centro de operaciones.
 *
 * Todd conoce el tablero: sabe qué está atrasado, ayuda a preparar la reunión y
 * puede proponer cambiar una tarea que no puedas cumplir. Cuando propone un cambio,
 * la respuesta trae una `accion` que la UI resuelve con Reemplazar / Descartar.
 */

export type ToddRole = "user" | "assistant"

export interface ToddMensaje {
  role: ToddRole
  content: string
  created_at: string
}

export interface ToddPropuesta {
  title: string
  description?: string
}

export interface ToddAccionCambio {
  tipo: "proponer_cambio"
  task_id: string
  propuesta: ToddPropuesta
}

export type ToddAccion = ToddAccionCambio | null

export interface ToddReply {
  reply: string
  accion: ToddAccion
}

// El backend puede responder `{ mensajes: [...] }` o un array directo: toleramos ambos.
interface MensajesEnvelope {
  mensajes?: ToddMensaje[]
}

/** Historial del chat con Todd. Devuelve [] si aún no hay nada. */
export async function getMensajesTodd(): Promise<ToddMensaje[]> {
  const r = await api.get<MensajesEnvelope | ToddMensaje[]>("/todd-secretario/mensajes")
  const data = r.data
  if (Array.isArray(data)) return data
  return data?.mensajes ?? []
}

/** Envía un mensaje a Todd y devuelve su respuesta (con posible acción). */
export async function enviarMensajeTodd(content: string): Promise<ToddReply> {
  const r = await api.post<ToddReply>("/todd-secretario/mensajes", { content })
  return {
    reply: r.data?.reply ?? "",
    accion: r.data?.accion ?? null,
  }
}
