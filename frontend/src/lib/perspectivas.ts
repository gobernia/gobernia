// frontend/src/lib/perspectivas.ts
import api from "@/lib/api"

export type Role = "empleado" | "directivo" | "socio" | "cliente" | "proveedor"

export const ROLE_LABEL: Record<Role, string> = {
  empleado: "Empleado clave", directivo: "Directivo", socio: "Socio",
  cliente: "Cliente", proveedor: "Proveedor / aliado",
}
export const ANONYMOUS_ROLES: Role[] = ["empleado", "cliente"]

export interface Invite {
  id: string; role: Role; invitee_name: string | null
  token: string; url?: string; status: "pending" | "active" | "done"; created_at: string
}

export interface PublicPerspectiva {
  role: Role; company_name: string
  /** Logo de la empresa como data URL, o null si no subieron uno. */
  logo?: string | null
  messages: { role: "todd" | "user"; text: string; options: string[] | null }[]
  done: boolean
}
export interface PerspectivaTurn {
  message: string; options: string[] | null; input: "text" | "single_choice"; done: boolean
}

export interface Sintesis {
  status: "none" | "generating" | "active" | "failed"
  coincidencias: string[]; contradicciones: string[]; puntos_ciegos: string[]
  por_rol: Record<string, string>; conteo: Record<string, number>
}

export async function createInvite(role: Role, name?: string): Promise<Invite> {
  const r = await api.post<Invite>("/perspectivas/invite", { role, name: name || null })
  return r.data
}
export async function listInvites(): Promise<Invite[]> {
  const r = await api.get<Invite[]>("/perspectivas")
  return r.data
}
export async function revokeInvite(id: string): Promise<void> {
  await api.delete(`/perspectivas/${id}`)
}
export async function consolidarPerspectivas(): Promise<void> {
  await api.post("/perspectivas/consolidar")
}
export async function getSintesis(): Promise<Sintesis> {
  const r = await api.get<Sintesis>("/perspectivas/sintesis")
  return r.data
}
export async function getPerspectiva(token: string): Promise<PublicPerspectiva> {
  const r = await api.get<PublicPerspectiva>(`/perspectiva/${token}`)
  return r.data
}
export async function answerPerspectiva(token: string, answer: string | null): Promise<PerspectivaTurn> {
  const r = await api.post<PerspectivaTurn>(`/perspectiva/${token}/turn`, { answer })
  return r.data
}
