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
  covered_keys: string[]
  objectives: Objective[]
}

export async function getOrdenDelDia(monthIndex: number): Promise<OrdenDelDia> {
  const r = await api.get<OrdenDelDia>(`/annual-plan/months/${monthIndex}/orden-del-dia`)
  return r.data
}

export async function markCoverage(monthIndex: number, themeKey: string, covered: boolean): Promise<void> {
  await api.post(`/annual-plan/months/${monthIndex}/coverage`, { theme_key: themeKey, covered })
}

export async function downloadOrdenPdf(monthIndex: number): Promise<void> {
  const r = await api.get(`/annual-plan/months/${monthIndex}/orden-del-dia/pdf`, { responseType: "blob" })
  const url = URL.createObjectURL(r.data as Blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `orden-del-dia-mes-${monthIndex}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
