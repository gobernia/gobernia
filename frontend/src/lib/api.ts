import axios from "axios"

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  headers: { "Content-Type": "application/json" },
})

let _token: string | null = null

export const setAuthToken = (token: string | null) => {
  _token = token
}

api.interceptors.request.use(config => {
  if (_token) config.headers.Authorization = `Bearer ${_token}`
  return config
})

export default api
