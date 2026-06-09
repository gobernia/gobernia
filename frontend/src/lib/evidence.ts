import api from "@/lib/api"

export interface Evidence {
  id: string
  action_task_id: string
  filename: string
  content_type: string
  size_bytes: number
  created_at: string
}

export async function getEvidence(taskId: string): Promise<Evidence[]> {
  const r = await api.get<Evidence[]>(`/tasks/${taskId}/evidence`)
  return r.data
}

export async function uploadEvidence(taskId: string, file: File): Promise<Evidence> {
  const form = new FormData()
  form.append("file", file)
  const r = await api.post<Evidence>(`/tasks/${taskId}/evidence`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  })
  return r.data
}

export async function deleteEvidence(evidenceId: string): Promise<void> {
  await api.delete(`/evidence/${evidenceId}`)
}
