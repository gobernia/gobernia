import api from "@/lib/api"

export const TODD_AREAS = ["estrategia", "comercial", "operativo", "rh", "financiero", "legal", "familiar"]

export interface ToddTurn {
  message: string
  options: string[] | null
  input: "text" | "single_choice"
  done: boolean
  areas_cubiertas: string[]
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
  areas_cubiertas: string[]
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

export async function editToddAnswer(answerIndex: number, nuevaRespuesta: string): Promise<ToddTurn> {
  const r = await api.post<ToddTurn>("/onboarding/todd/edit",
    { answer_index: answerIndex, nueva_respuesta: nuevaRespuesta })
  return r.data
}

export async function closeTodd(): Promise<void> {
  await api.post("/onboarding/todd/close")
}

export const PESTEL_CATS = ["politicos", "economicos", "sociales", "tecnologicos", "ambiental", "legal"]

export async function getExternoSession(): Promise<ToddSession | null> {
  const r = await api.get("/onboarding/todd/externo", { validateStatus: s => s === 200 || s === 204 })
  if (r.status === 204) return null
  return r.data as ToddSession
}
export async function sendExternoAnswer(answer: string | null): Promise<ToddTurn> {
  const r = await api.post<ToddTurn>("/onboarding/todd/externo/turn", { answer })
  return r.data
}
export async function editExternoAnswer(answerIndex: number, nuevaRespuesta: string): Promise<ToddTurn> {
  const r = await api.post<ToddTurn>("/onboarding/todd/externo/edit",
    { answer_index: answerIndex, nueva_respuesta: nuevaRespuesta })
  return r.data
}
export async function getMetas(): Promise<string[]> {
  const r = await api.get<{ metas: string[] }>("/onboarding/todd/metas")
  return r.data.metas
}
export async function saveMetas(orden: string[]): Promise<void> {
  await api.post("/onboarding/todd/metas", { orden })
}

// Pares {pregunta de Todd, respuesta del usuario} con el índice (en messages) de la respuesta.
export interface QAPair { msgIndex: number; question: string; answer: string; options: string[] | null }

export function buildQAPairs(messages: ToddMessage[]): QAPair[] {
  const pairs: QAPair[] = []
  for (let i = 0; i < messages.length; i++) {
    if (messages[i].role === "user") {
      const q = i > 0 ? messages[i - 1] : null
      pairs.push({
        msgIndex: i,
        question: q?.text ?? "",
        answer: messages[i].text,
        options: q?.options ?? null,
      })
    }
  }
  return pairs
}
