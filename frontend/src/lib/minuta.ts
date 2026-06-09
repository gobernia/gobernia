import api from "@/lib/api"

export interface MinutaDecision {
  pregunta: string
  opcion_a: string
  opcion_b: string
  decision_tomada: string | null
}

export interface MinutaCompromiso {
  descripcion: string
  fecha: string
}

export interface MinutaTema {
  id: number
  titulo: string
  sintesis: string
  decision: MinutaDecision
  compromiso: MinutaCompromiso | null
}

export interface MinutaOut {
  generada: boolean
  carta: string
  temas: MinutaTema[]
}

export async function getMinuta(): Promise<MinutaOut> {
  const r = await api.get<MinutaOut>("/annual-plan/minuta")
  return r.data
}

export async function sesionarConsejo(): Promise<MinutaOut> {
  const r = await api.post<MinutaOut>("/annual-plan/minuta")
  return r.data
}

export async function cerrarDecision(temaId: number, decision: "A" | "B" | "aplazar"): Promise<MinutaOut> {
  const r = await api.post<MinutaOut>("/annual-plan/minuta/decision", { tema_id: temaId, decision })
  return r.data
}
