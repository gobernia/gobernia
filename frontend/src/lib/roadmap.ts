// frontend/src/lib/roadmap.ts
import api from "@/lib/api"

export interface Meta3a { meta: string; kpi: string | null; valor_actual: string | null; target: string }
export interface Pilar {
  nombre: string; descripcion: string
  milestones: { anio1: string[]; anio2: string[]; anio3: string[] }
}
export interface Roadmap {
  vision: string; mision: string; propuesta_valor: string
  metas_3anios: Meta3a[]; resumen_foda: string; resumen_entorno: string; pilares: Pilar[]
}

const EMPTY: Roadmap = {
  vision: "", mision: "", propuesta_valor: "", metas_3anios: [],
  resumen_foda: "", resumen_entorno: "", pilares: [],
}

export async function getRoadmap(): Promise<Roadmap> {
  const r = await api.get<Partial<Roadmap>>("/annual-plan/roadmap")
  return { ...EMPTY, ...(r.data || {}) }
}

export async function saveRoadmap(roadmap: Roadmap): Promise<Roadmap> {
  const r = await api.patch<Roadmap>("/annual-plan/roadmap", roadmap)
  return { ...EMPTY, ...(r.data || {}) }
}

export async function downloadRoadmapPdf(): Promise<void> {
  const r = await api.get("/annual-plan/roadmap/pdf", { responseType: "blob" })
  const url = URL.createObjectURL(r.data as Blob)
  const a = document.createElement("a")
  a.href = url; a.download = "roadmap.pdf"
  document.body.appendChild(a); a.click(); a.remove()
  URL.revokeObjectURL(url)
}
