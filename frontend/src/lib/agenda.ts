import api from "@/lib/api"

export interface AgendaItem {
  orden: number
  titulo: string
  area: string
  detector: string
  impacto: string
  urgencia: string
  racional: string
  evidencia: string[]
  score: number
}

export async function getAgenda(): Promise<AgendaItem[]> {
  const r = await api.get<AgendaItem[]>("/annual-plan/agenda")
  return r.data
}
