import api from "@/lib/api"

export type CoverageEstado = "en_tiempo" | "riesgo" | "atrasado" | "critico"

export interface CoverageRow {
  key: string
  label: string
  type: string
  frecuencia_anual: number
  esperadas: number
  realizadas: number
  estado: CoverageEstado
}

export async function getCobertura(): Promise<CoverageRow[]> {
  const r = await api.get<CoverageRow[]>("/annual-plan/cobertura")
  return r.data
}
