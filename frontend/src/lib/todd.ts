import api from "@/lib/api"

export interface ToddTurn {
  message: string
  options: string[] | null
  input: "text" | "single_choice"
  done: boolean
}

export interface ToddMessage {
  role: "todd" | "user"
  text: string
  options: string[] | null
}

export interface ToddSession {
  status: string
  messages: ToddMessage[]
  done: boolean
}

export async function getToddSession(): Promise<ToddSession | null> {
  const r = await api.get("/onboarding/todd", { validateStatus: s => s === 200 || s === 204 })
  if (r.status === 204) return null
  return r.data as ToddSession
}

export async function sendToddAnswer(answer: string | null): Promise<ToddTurn> {
  const r = await api.post<ToddTurn>("/onboarding/todd/turn", { answer })
  return r.data
}

export async function closeTodd(): Promise<void> {
  await api.post("/onboarding/todd/close")
}
