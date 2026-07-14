import api from "@/lib/api"

export type BoardDocType = "financial" | "presentation" | "audit_plan" | "other"

export const BOARD_DOC_TYPES: { value: BoardDocType; label: string; hint: string }[] = [
  { value: "financial",    label: "Estados financieros", hint: "Balance, estado de resultados, flujo de efectivo" },
  { value: "presentation", label: "Presentación",        hint: "El deck que llevas a la sesión" },
  { value: "audit_plan",   label: "Plan de auditoría",   hint: "Programa o informe de auditoría" },
  { value: "other",        label: "Otro documento",      hint: "Cualquier material de apoyo" },
]

export interface BoardDoc {
  id: string
  filename: string
  document_type: string
  document_type_label: string
  created_at: string
}

export async function listBoardDocs(sessionId: string): Promise<BoardDoc[]> {
  const r = await api.get<{ items: BoardDoc[] }>(`/board-sessions/${sessionId}/documents`)
  return r.data?.items ?? []
}

export async function uploadBoardDoc(
  sessionId: string,
  file: File,
  documentType: BoardDocType,
): Promise<BoardDoc> {
  const form = new FormData()
  form.append("file", file)
  form.append("document_type", documentType)
  const r = await api.post<BoardDoc>(`/board-sessions/${sessionId}/documents`, form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000,
  })
  return r.data
}

export async function deleteBoardDoc(sessionId: string, docId: string): Promise<void> {
  await api.delete(`/board-sessions/${sessionId}/documents/${docId}`)
}
