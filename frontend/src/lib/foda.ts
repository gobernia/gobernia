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

export async function downloadFodaPdf(): Promise<void> {
  const r = await api.get("/onboarding/foda/pdf", { responseType: "blob" })
  const url = URL.createObjectURL(r.data as Blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "matriz-foda.pdf"
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
