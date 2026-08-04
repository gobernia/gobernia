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

// Público por token: genera (o devuelve cacheada) la explicación de una tarea.
export async function explicarTarea(
  token: string,
  taskId: string,
): Promise<ExplicacionTarea> {
  const r = await publicApi.post<ExplicacionTarea>(`/t/${token}/tareas/${taskId}/explicar`)
  return r.data
}
