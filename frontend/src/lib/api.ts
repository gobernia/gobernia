import axios from "axios"
import { supabase } from "@/lib/supabase"

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  headers: { "Content-Type": "application/json" },
})

let _token: string | null = null

export const setAuthToken = (token: string | null) => {
  _token = token
}

api.interceptors.request.use(async config => {
  // En una recarga completa, AuthSync aún no alcanzó a setear el token cuando
  // sale la primera request. Si falta, lo obtenemos directo de Supabase para no
  // mandar la petición sin Authorization (evita el 401 del primer fetch tras recargar).
  if (!_token) {
    try {
      const { data } = await supabase.auth.getSession()
      _token = data.session?.access_token ?? null
    } catch {
      /* sin sesión: la request saldrá sin token y el backend responderá 401 */
    }
  }
  if (_token) config.headers.Authorization = `Bearer ${_token}`
  return config
})

export default api
