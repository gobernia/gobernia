import api from "@/lib/api"

export interface DocumentoBiblioteca {
  tipo: string
  titulo: string
  descripcion: string
  validado_at: string | null
  estado: string
  pdf_path: string
}

export async function getBiblioteca(): Promise<DocumentoBiblioteca[]> {
  const r = await api.get<{ items: DocumentoBiblioteca[] }>("/biblioteca")
  return r.data?.items ?? []
}
