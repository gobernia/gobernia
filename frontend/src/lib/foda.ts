import api from "@/lib/api"

export interface Foda {
  fortalezas: string[]
  oportunidades: string[]
  debilidades: string[]
  amenazas: string[]
  sintesis: string
  metas_priorizadas: string[]
}

export interface FodaOut {
  status: "none" | "generating" | "active" | "failed"
  foda: Foda | null
  metas: string[]
}

export async function getFoda(): Promise<FodaOut> {
  const r = await api.get<FodaOut>("/onboarding/foda", { validateStatus: s => s === 200 || s === 404 })
  if (r.status === 404) return { status: "none", foda: null, metas: [] }
  return r.data
}
