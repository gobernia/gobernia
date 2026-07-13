// frontend/src/lib/roadmap.ts
import api from "@/lib/api"

export interface Meta3a { meta: string; kpi: string | null; valor_actual: string | null; target: string }

/** KPI de un pilar: valor de hoy → meta. `meta` puede venir vacía ("por definir"). */
export interface KpiPilar { label: string; actual: string; meta: string }
/** Resultado esperado de un pilar: título corto (ej. "↑ Margen bruto") + descripción. */
export interface ResultadoEsperado { titulo: string; descripcion: string }
/** Título de la fase de cada año dentro de un pilar. */
export interface Fase {
  anio1?: { titulo?: string }
  anio2?: { titulo?: string }
  anio3?: { titulo?: string }
}

export interface Pilar {
  nombre: string; descripcion: string
  milestones: { anio1: string[]; anio2: string[]; anio3: string[] }
  // Campos opcionales (plantilla de presentación estratégica). Un roadmap viejo no los trae.
  objetivo?: string
  estrategias?: string[]
  kpis?: KpiPilar[]
  resultados_esperados?: ResultadoEsperado[]
  fases?: Fase
}

/** Lema de cada año del recorrido (ej. "Ordenar la casa"). */
export interface TemasPorAnio { anio1?: string; anio2?: string; anio3?: string }

export interface Roadmap {
  vision: string; mision: string; propuesta_valor: string
  metas_3anios: Meta3a[]; resumen_foda: string; resumen_entorno: string; pilares: Pilar[]
  // Campos opcionales globales.
  anio_objetivo?: number
  objetivos_estrategicos?: string[]
  key_enablers?: string[]
  temas_por_anio?: TemasPorAnio
  conclusion_diagnostico?: string
  conclusion_entorno?: string
}

const EMPTY: Roadmap = {
  vision: "", mision: "", propuesta_valor: "", metas_3anios: [],
  resumen_foda: "", resumen_entorno: "", pilares: [],
  objetivos_estrategicos: [], key_enablers: [], temas_por_anio: {},
  conclusion_diagnostico: "", conclusion_entorno: "",
}

export async function getRoadmap(): Promise<Roadmap> {
  const r = await api.get<Partial<Roadmap>>("/annual-plan/roadmap")
  return { ...EMPTY, ...(r.data || {}) }
}

export async function saveRoadmap(roadmap: Roadmap): Promise<Roadmap> {
  const r = await api.patch<Roadmap>("/annual-plan/roadmap", roadmap)
  return { ...EMPTY, ...(r.data || {}) }
}

export type RoadmapStatus = "borrador" | "validado"
export interface RoadmapEstado { status: RoadmapStatus; validated_at: string | null }

export async function getRoadmapEstado(): Promise<RoadmapEstado> {
  const r = await api.get<RoadmapEstado>("/annual-plan/roadmap/estado")
  return { status: r.data?.status ?? "borrador", validated_at: r.data?.validated_at ?? null }
}

/** Sella el roadmap: queda solo lectura y se registra para la próxima sesión de consejo. */
export async function validarRoadmap(): Promise<RoadmapEstado> {
  const r = await api.post<RoadmapEstado>("/annual-plan/roadmap/validar")
  return r.data
}

/** Vuelve a borrador para poder editarlo (hay que validarlo de nuevo). */
export async function reabrirRoadmap(): Promise<RoadmapEstado> {
  const r = await api.post<RoadmapEstado>("/annual-plan/roadmap/reabrir")
  return r.data
}

export async function downloadRoadmapPdf(): Promise<void> {
  const r = await api.get("/annual-plan/roadmap/pdf", { responseType: "blob" })
  const url = URL.createObjectURL(r.data as Blob)
  const a = document.createElement("a")
  a.href = url; a.download = "roadmap.pdf"
  document.body.appendChild(a); a.click(); a.remove()
  URL.revokeObjectURL(url)
}
