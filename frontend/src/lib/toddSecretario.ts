import api from "@/lib/api"
import { supabase } from "@/lib/supabase"

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

export type ToddEvento =
  | { t: "texto"; d: string }
  | { t: "leyendo"; doc: string }
  | { t: "fin"; accion: ToddAccion }
  | { t: "error" }

/**
 * Envía un mensaje a Todd y va entregando su respuesta MIENTRAS la escribe (como ChatGPT):
 * fragmentos de texto, aviso cuando abre un documento y, al final, la posible acción.
 */
export async function streamMensajeTodd(content: string, onEvento: (e: ToddEvento) => void): Promise<void> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const res = await fetch(`${api.defaults.baseURL}/todd-secretario/mensajes/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ content }),
  })
  if (!res.ok || !res.body) throw new Error(`stream ${res.status}`)
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let pendiente = ""
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    pendiente += decoder.decode(value, { stream: true })
    const lineas = pendiente.split("\n")
    pendiente = lineas.pop() ?? ""
    for (const l of lineas) if (l.trim()) onEvento(JSON.parse(l) as ToddEvento)
  }
  if (pendiente.trim()) onEvento(JSON.parse(pendiente) as ToddEvento)
}
