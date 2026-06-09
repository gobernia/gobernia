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

export interface AgendaOut {
  curada: boolean
  carta: string
  items: AgendaItem[]
}

export async function getAgenda(): Promise<AgendaOut> {
  const r = await api.get<AgendaOut>("/annual-plan/agenda")
  return r.data
}

export async function convocarChair(): Promise<AgendaOut> {
  const r = await api.post<AgendaOut>("/annual-plan/agenda/chair")
  return r.data
}
