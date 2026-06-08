import api from "@/lib/api"
import type { Objective } from "@/lib/annualPlan"

export interface ThemeRef {
  key: string
  label: string
  every_n_sessions: number | null
}

export interface OrdenDelDia {
  month_index: number
  period_year: number
  period_month: number
  permanent_themes: ThemeRef[]
  coverage_themes: ThemeRef[]
  objectives: Objective[]
}

export async function getOrdenDelDia(monthIndex: number): Promise<OrdenDelDia> {
  const r = await api.get<OrdenDelDia>(`/annual-plan/months/${monthIndex}/orden-del-dia`)
  return r.data
}
