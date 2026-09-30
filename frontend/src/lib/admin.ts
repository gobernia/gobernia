// Panel de super admin (solo lectura). Acceso restringido en el servidor.
import api from "@/lib/api"

export interface AdminUsuario {
  id: string
  email: string
  registrado: string
  ultimo_acceso: string | null
  empresa: string | null
  industria: string | null
  etapa: string
  plan_estado: string | null
  periodicidad: string | null
  sesiones: number
  ultima_sesion: string | null
  tareas_total: number
  tareas_completadas: number
  documentos: number
}

export interface AdminResumen {
  usuarios_total: number
  nuevos_7d: number
  nuevos_30d: number
  activos_7d: number
  activos_30d: number
  sesiones_total: number
  con_plan: number
  embudo: { etapa: string; label: string; usuarios: number }[]
  etapas: { etapa: string; label: string }[]
  usuarios: AdminUsuario[]
  cobros_activos: boolean
}

export async function esAdmin(): Promise<boolean> {
  try {
    const r = await api.get<{ es_admin: boolean }>("/admin/me")
    return !!r.data?.es_admin
  } catch {
    return false
  }
}

export async function getAdminResumen(): Promise<AdminResumen> {
  const r = await api.get<AdminResumen>("/admin/resumen")
  return r.data
}
