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

export interface Diagnostico {
  status: DiagnosticoStatus
  fail_reason: string | null
  sections: DiagnosticoSection[]
  sources: DiagnosticoSource[]
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
  return r.data
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
