import api from "@/lib/api"

export type DiagnosticoStatus = "generating" | "active" | "failed"

export interface DiagnosticoSection {
  key: string
  title: string
  body: string
}

export interface DiagnosticoSource {
  title: string
  url: string
}

export interface Hallazgo {
  tipo: string
  texto: string
}

/** Normaliza un hallazgo (de cualquier forma que produzca el modelo de Todd) a Hallazgo[].
 * Tolera: {nota/texto, clasificacion/tipo}, lista de dichos objetos, lista de strings o string. */
function toHallazgos(value: unknown): Hallazgo[] {
  const one = (v: unknown): Hallazgo | null => {
    if (v && typeof v === "object" && !Array.isArray(v)) {
      const o = v as Record<string, unknown>
      const tipo = String(o.tipo ?? o.clasificacion ?? "").toLowerCase().trim()
      const texto = String(o.texto ?? o.nota ?? o.detalle ?? "").trim()
      return texto ? { tipo, texto } : null
    }
    const texto = String(v ?? "").trim()
    return texto ? { tipo: "", texto } : null
  }
  if (Array.isArray(value)) {
    return value.map(one).filter((x): x is Hallazgo => x !== null)
  }
  const single = one(value)
  return single ? [single] : []
}

export function normalizeHallazgos(raw: unknown): Record<string, Hallazgo[]> {
  const out: Record<string, Hallazgo[]> = {}
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    for (const [area, value] of Object.entries(raw as Record<string, unknown>)) {
      const list = toHallazgos(value)
      if (list.length) out[area] = list
    }
  }
  return out
}

export interface Diagnostico {
  status: DiagnosticoStatus
  fail_reason: string | null
  sections: DiagnosticoSection[]
  sources: DiagnosticoSource[]
  fortalezas_debilidades: Record<string, Hallazgo[]>
}

export interface DiagnosticoStatusOut {
  status: DiagnosticoStatus
  fail_reason: string | null
}

export async function getDiagnosticoStatus(): Promise<DiagnosticoStatusOut> {
  const r = await api.get<DiagnosticoStatusOut>("/diagnostico/status")
  return r.data
}

export async function getDiagnostico(): Promise<Diagnostico> {
  const r = await api.get<Diagnostico>("/diagnostico")
  return { ...r.data, fortalezas_debilidades: normalizeHallazgos(r.data.fortalezas_debilidades) }
}

export async function generateDiagnostico(): Promise<DiagnosticoStatusOut> {
  const r = await api.post<DiagnosticoStatusOut>("/diagnostico/generate")
  return r.data
}

export async function downloadDiagnosticoPdf(): Promise<void> {
  const r = await api.get("/diagnostico/pdf", { responseType: "blob" })
  const url = URL.createObjectURL(r.data as Blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "diagnostico.pdf"
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
