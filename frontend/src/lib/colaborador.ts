import axios from "axios"
import api from "@/lib/api"
import { ExplicacionTarea } from "@/lib/annualPlan"

// Cliente sin interceptor de auth para los endpoints públicos por token (/t/{token}).
const publicApi = axios.create({ baseURL: api.defaults.baseURL })

export type { ExplicacionTarea }

export interface TareaColab {
  id: string
  title: string
  description: string | null
  status: string
  due_date: string | null
  objetivo: string | null
  explicacion: ExplicacionTarea | null
  tiene_explicacion: boolean
  /** Documentos que ya tiene la tarea y lo que dijo el Auditor al leerlos. */
  evidencias?: number
  validacion?: ValidacionColab | null
}

export interface ValidacionColab {
  estado: "validada" | "parcial" | "insuficiente" | "sin_revisar" | "revisando"
  motivo?: string
  documento?: string
  otro_documento?: boolean
  cubre?: string
  falta?: string
  alternativas?: string[]
}

export interface Escritorio {
  nombre: string | null
  empresa: string | null
  tareas: TareaColab[]
}

// Owner-side (autenticado): crea/obtiene el enlace de las tareas de un correo.
export async function getColaboradorLink(
  email: string,
  nombre?: string | null,
): Promise<{ token: string }> {
  const r = await api.post<{ token: string }>("/colaboradores/link", { email, nombre })
  return r.data
}

// Público por token: el escritorio del responsable.
export async function getEscritorio(token: string): Promise<Escritorio> {
  const r = await publicApi.get<Escritorio>(`/t/${token}`)
  return r.data
}

// Público por token: el responsable sube la evidencia de SU tarea (el Auditor la lee al momento).
export async function subirEvidenciaColab(token: string, taskId: string, file: File): Promise<void> {
  const fd = new FormData()
  fd.append("file", file)
  await publicApi.post(`/t/${token}/tareas/${taskId}/evidencia`, fd)
}

// Público por token: "¿Qué subo?" de una tarea del responsable (se genera una vez y se guarda).
export async function queSubirColab(
  token: string, taskId: string,
): Promise<{ pide: string; alternativas: string[]; sin_documento: string }> {
  const r = await publicApi.post(`/t/${token}/tareas/${taskId}/que-subir`)
  return r.data
}

// Público por token: genera (o devuelve cacheada) la explicación de una tarea.
export async function explicarTarea(
  token: string,
  taskId: string,
): Promise<ExplicacionTarea> {
  const r = await publicApi.post<ExplicacionTarea>(`/t/${token}/tareas/${taskId}/explicar`)
  return r.data
}

export interface ToddMensaje {
  role: string
  content: string
}

// Público por token: historial del chat de Todd para el responsable.
export async function getToddChat(
  token: string,
): Promise<{ mensajes: ToddMensaje[] }> {
  const r = await publicApi.get<{ mensajes: ToddMensaje[] }>(`/t/${token}/todd`)
  return r.data
}

// Público por token: envía un mensaje a Todd y recibe su respuesta + historial.
export async function enviarToddResponsable(
  token: string,
  mensaje: string,
): Promise<{ reply: string; mensajes: ToddMensaje[]; avance_guardado?: boolean }> {
  const r = await publicApi.post<{ reply: string; mensajes: ToddMensaje[]; avance_guardado?: boolean }>(
    `/t/${token}/todd`,
    { mensaje },
  )
  return r.data
}
