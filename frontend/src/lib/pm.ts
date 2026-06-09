import axios from "axios"
import api from "@/lib/api"

// Cliente sin interceptor de auth para los endpoints públicos por token.
const publicApi = axios.create({ baseURL: api.defaults.baseURL })

export interface AvanceItem {
  fecha: string
  pct: number
  nota: string | null
  evidencia_url: string | null
}

export interface Compromiso {
  id: string
  descripcion: string
  responsable_email: string | null
  responsable_nombre: string | null
  fecha_compromiso: string | null
  status: string
  nudge: string
  token: string
  avances: AvanceItem[]
}

export interface CompromisoPublic {
  descripcion: string
  fecha_compromiso: string | null
  status: string
  avances: AvanceItem[]
}

export async function getCompromisos(): Promise<Compromiso[]> {
  const r = await api.get<Compromiso[]>("/pm/compromisos")
  return r.data
}

export async function patchCompromiso(
  id: string,
  body: { responsable_email?: string; responsable_nombre?: string; fecha_compromiso?: string },
): Promise<Compromiso> {
  const r = await api.patch<Compromiso>(`/pm/compromisos/${id}`, body)
  return r.data
}

export async function getCompromisoPublico(token: string): Promise<CompromisoPublic> {
  const r = await publicApi.get<CompromisoPublic>(`/pm/c/${token}`)
  return r.data
}

export async function reportarAvance(
  token: string,
  body: { pct: number; nota?: string; evidencia_url?: string },
): Promise<CompromisoPublic> {
  const r = await publicApi.post<CompromisoPublic>(`/pm/c/${token}/avance`, body)
  return r.data
}
