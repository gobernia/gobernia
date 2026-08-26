import api from "@/lib/api"

/**
 * El tablero del plan mensual — la vista tipo Monday del Centro de operaciones.
 *
 * Alimenta el `<TableroPlan/>` del consejo: cada mes es un grupo con sus tareas,
 * y el estado de cada tarea se cambia sin candado (a diferencia del Plan).
 */

export type TaskStatus = "pendiente" | "en_progreso" | "completada"
export type TaskPriority = "alta" | "media" | "baja"

// Resultado de la validación de una tarea por el Consejo al sesionar el mes.
export type ValidacionEstado = "validada" | "insuficiente" | "sin_revisar"
export interface Validacion {
  estado: ValidacionEstado
  motivo: string
}

export interface BoardTask {
  id: string
  title: string
  owner: string | null
  owner_email: string | null
  status: TaskStatus
  priority: TaskPriority
  due_date: string | null
  objetivo: string | null
  // Índice del pilar del roadmap que la tarea hace avanzar (None si no se determinó).
  pilar_index?: number | null
  // False = quedó FUERA del Plan anual aprobado (pendiente sin ejecutar).
  incluida?: boolean
  // ── Agenda de gobierno: cada tarea es un punto del Orden del Día ──
  // Consejero IA que lidera el análisis del punto (CFO|CSO|CRO|Auditor).
  lead_agent?: string | null
  // informacion | seguimiento | deliberacion | decision.
  agenda_type?: string | null
  // Decisión/recomendación esperada de la sesión, si aplica.
  decision_expected?: string | null
  // Si la tarea se arrastró de un mes anterior, de dónde viene (p.ej. "Marzo 2026").
  viene_de?: string | null
  // Cuántos documentos de evidencia tiene la tarea.
  evidencias?: number
  // Última validación del Consejo (null si nunca se validó).
  validacion?: Validacion | null
}

export interface BoardMes {
  month_index: number
  period_year: number
  period_month: number
  label: string
  es_mes_actual: boolean
  tareas: BoardTask[]
  // Tareas incompletas de meses anteriores que "se pasan" a este mes.
  arrastradas?: BoardTask[]
}

interface BoardResponse {
  meses: BoardMes[]
  // Tareas que quedaron FUERA del plan del año (pendientes sin ejecutar).
  pendientes?: BoardTask[]
}

/** El tablero completo, agrupado por mes. */
export async function getBoard(): Promise<BoardMes[]> {
  const r = await api.get<BoardResponse>("/annual-plan/board")
  return r.data?.meses ?? []
}

/** El tablero + las tareas pendientes fuera del plan (para el banco del Board). */
export async function getBoardFull(): Promise<{ meses: BoardMes[]; pendientes: BoardTask[] }> {
  const r = await api.get<BoardResponse>("/annual-plan/board")
  return { meses: r.data?.meses ?? [], pendientes: r.data?.pendientes ?? [] }
}

/** Mete o saca una tarea del plan del año (False = pendiente fuera del plan). */
export async function setTaskIncluida(taskId: string, incluida: boolean): Promise<BoardTask> {
  const r = await api.patch<BoardTask>(`/tasks/${taskId}/incluida`, { incluida })
  return r.data
}

/** Elimina una tarea por completo (con sus evidencias). Irreversible. */
export async function eliminarTarea(taskId: string): Promise<void> {
  await api.delete(`/tasks/${taskId}`)
}

/** Cambia el estado de una tarea. Sin candado de evidencia. */
export async function setTaskEstado(taskId: string, status: TaskStatus): Promise<BoardTask> {
  const r = await api.patch<BoardTask>(`/tasks/${taskId}/estado`, { status })
  return r.data
}

/** Cambia el responsable de una tarea (y opcionalmente su correo). Devuelve la tarea actualizada. */
export async function setTaskOwner(taskId: string, owner: string, ownerEmail?: string | null): Promise<BoardTask> {
  const r = await api.patch<BoardTask>(`/tasks/${taskId}`, { owner, owner_email: ownerEmail ?? null })
  return r.data
}

interface BoardSessionRef {
  board_session_id: string
  period_year: number
  period_month: number
}

/**
 * Abre (o crea) la sesión del Consejo para un periodo y devuelve su id.
 *
 * Si el backend responde 409 porque la sesión ya existe, recupera su id: primero
 * del `detail`, y si no, volviendo a consultar el listado de sesiones.
 */
export async function abrirSesionMes(year: number, month: number): Promise<string> {
  try {
    const r = await api.post<BoardSessionRef>("/board-sessions", { period_year: year, period_month: month })
    return r.data.board_session_id
  } catch (e: unknown) {
    const res = (e as { response?: { status?: number; data?: { detail?: unknown } } })?.response
    if (res?.status !== 409) throw e

    // El id puede venir dentro del detail (objeto) del 409.
    const detail = res.data?.detail
    if (detail && typeof detail === "object") {
      const d = detail as Record<string, unknown>
      const id = d.board_session_id ?? d.id
      if (typeof id === "string") return id
    }

    // Si no vino el id, lo buscamos en el listado por periodo.
    const list = await api.get<BoardSessionRef[]>("/board-sessions")
    const found = (list.data ?? []).find(s => s.period_year === year && s.period_month === month)
    if (found) return found.board_session_id

    throw e
  }
}

/**
 * Descarga el acta HISTÓRICA (PDF) de una sesión de consejo: la foto inmutable
 * congelada al primer descargue de esa sesión. Mismo patrón blob que `downloadOrdenPdf`.
 */
export async function downloadSesionActaPdf(sessionId: string): Promise<void> {
  const r = await api.get(`/board-sessions/${sessionId}/acta/pdf`, { responseType: "blob" })
  const url = URL.createObjectURL(r.data as Blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "acta-sesion.pdf"
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
