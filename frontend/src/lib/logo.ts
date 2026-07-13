// frontend/src/lib/logo.ts
import api from "@/lib/api"

export interface CompanyLogo {
  has_logo: boolean
  /** Data URL listo para <img src>, o null si no hay logo. */
  logo: string | null
}

/** Tamaño máximo aceptado por el backend (1 MB). */
export const LOGO_MAX_BYTES = 1024 * 1024
export const LOGO_ACCEPT = ".png,.jpg,.jpeg"

export async function getLogo(): Promise<CompanyLogo> {
  const r = await api.get<CompanyLogo>("/company/logo")
  return r.data
}

export async function uploadLogo(file: File): Promise<CompanyLogo> {
  const form = new FormData()
  form.append("file", file)
  const r = await api.post<CompanyLogo>("/company/logo", form, {
    headers: { "Content-Type": "multipart/form-data" },
  })
  return r.data
}

export async function deleteLogo(): Promise<CompanyLogo> {
  const r = await api.delete<CompanyLogo>("/company/logo")
  return r.data
}
