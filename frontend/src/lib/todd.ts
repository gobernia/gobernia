import api from "@/lib/api"
import { supabase } from "@/lib/supabase"

export const TODD_AREAS = ["estrategia", "comercial", "operativo", "rh", "financiero", "legal", "familiar"]

export interface ToddTurn {
  message: string
  options: string[] | null
  input: "text" | "single_choice"
  done: boolean
  areas_cubiertas: string[]
  expects_detail?: boolean
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

// ── Turnos EN VIVO ─────────────────────────────────────────────────────────────────────
// La pregunta de Todd llega mientras la IA termina de escribir el expediente de la empresa
// (que en una entrevista avanzada tarda 10+ s). El turno que se guarda es el mismo de siempre.

/** Lo que ya se ve del siguiente turno mientras Todd lo escribe. */
export interface ToddEnVivo {
  message: string
  options?: string[] | null
  input?: "text" | "single_choice"
}

/** Todd no pudo generar la pregunta (la IA falló): igual que cuando falla el envío normal. */
export class ErrorDeTodd extends Error {}
/** El servidor no ofrece la vía en vivo (p. ej. versión anterior): se usa la normal. */
class SinVivo extends Error {}

function leerEvento(bloque: string): { evento: string; datos: unknown } | null {
  let evento = "", datos = ""
  for (const linea of bloque.split("\n")) {
    if (linea.startsWith("event: ")) evento = linea.slice(7)
    else if (linea.startsWith("data: ")) datos += linea.slice(6)
  }
  if (!evento || !datos) return null // latidos (": sigo") y bloques vacíos
  return { evento, datos: JSON.parse(datos) }
}

async function turnoEnVivo(ruta: string, answer: string | null, alAvanzar: (p: ToddEnVivo) => void): Promise<ToddTurn> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const res = await fetch(`${api.defaults.baseURL}${ruta}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ answer }),
  })
  if (!res.ok || !res.body) throw new SinVivo(`HTTP ${res.status}`)
  const lector = res.body.getReader()
  const decod = new TextDecoder()
  let pendiente = ""
  for (;;) {
    const { value, done } = await lector.read()
    if (done) break
    pendiente += decod.decode(value, { stream: true })
    let corte: number
    while ((corte = pendiente.indexOf("\n\n")) >= 0) {
      const ev = leerEvento(pendiente.slice(0, corte))
      pendiente = pendiente.slice(corte + 2)
      if (!ev) continue
      if (ev.evento === "pregunta") alAvanzar(ev.datos as ToddEnVivo)
      else if (ev.evento === "fin") return ev.datos as ToddTurn
      else if (ev.evento === "error") throw new ErrorDeTodd(String((ev.datos as { detail?: string }).detail ?? ""))
    }
  }
  throw new Error("La conexión se cortó antes de terminar el turno")
}

function turnoDeSesion(s: ToddSession): ToddTurn {
  const ultimo = s.messages[s.messages.length - 1]
  return { message: ultimo.text, options: ultimo.options, input: ultimo.options ? "single_choice" : "text",
    done: s.done, areas_cubiertas: s.areas_cubiertas }
}

/** Manda la respuesta por la vía en vivo; si no se puede, por la normal, sin duplicar la
 *  respuesta: si la conexión se cortó a medias, primero revisa si el turno ya quedó guardado. */
async function conRespaldo(
  ruta: string, answer: string | null, alAvanzar: (p: ToddEnVivo) => void,
  normal: () => Promise<ToddTurn>, sesion: () => Promise<ToddSession | null>,
): Promise<ToddTurn> {
  try {
    return await turnoEnVivo(ruta, answer, alAvanzar)
  } catch (e) {
    if (e instanceof ErrorDeTodd) throw e
    if (e instanceof SinVivo) return normal()
    const s = await sesion().catch(() => null)
    const n = s?.messages.length ?? 0
    const ultimo = n ? s!.messages[n - 1] : null
    const previo = n > 1 ? s!.messages[n - 2] : null
    const yaGuardado = ultimo?.role === "todd" && (answer === null ? n === 1 : previo?.role === "user" && previo.text === answer)
    return yaGuardado ? turnoDeSesion(s!) : normal()
  }
}

export function sendToddAnswerEnVivo(answer: string | null, alAvanzar: (p: ToddEnVivo) => void): Promise<ToddTurn> {
  return conRespaldo("/onboarding/todd/turn/stream", answer, alAvanzar, () => sendToddAnswer(answer), getToddSession)
}

export function sendExternoAnswerEnVivo(answer: string | null, alAvanzar: (p: ToddEnVivo) => void): Promise<ToddTurn> {
  return conRespaldo("/onboarding/todd/externo/turn/stream", answer, alAvanzar, () => sendExternoAnswer(answer), getExternoSession)
}
