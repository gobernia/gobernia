// Repositorio general de documentos del usuario — alimenta los análisis de
// los consejeros. Da servicio a la pestaña "Mis consejeros".
import api from "@/lib/api"

export interface DocumentoRepo {
  document_id: string
  filename: string
  document_type: string
  document_type_label: string
  status: string
  created_at: string | null
}

export interface TipoDocumento { value: string; label: string }

export async function getDocumentos(): Promise<{ items: DocumentoRepo[]; types: TipoDocumento[] }> {
  const r = await api.get<{ items: DocumentoRepo[]; types: TipoDocumento[] }>("/documents")
  return { items: r.data?.items ?? [], types: r.data?.types ?? [] }
}

export async function subirDocumento(file: File, documentType: string): Promise<DocumentoRepo> {
  const form = new FormData()
  form.append("file", file)
  form.append("document_type", documentType)
  const r = await api.post<DocumentoRepo>("/documents/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  })
  return r.data
}

export async function eliminarDocumento(documentId: string): Promise<void> {
  await api.delete(`/documents/${documentId}`)
}
