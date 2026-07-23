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
  status: TaskStatus
  priority: TaskPriority
  due_date: string | null
  objetivo: string | null
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
}

/** El tablero completo, agrupado por mes. */
export async function getBoard(): Promise<BoardMes[]> {
  const r = await api.get<BoardResponse>("/annual-plan/board")
  return r.data?.meses ?? []
}

/** Cambia el estado de una tarea. Sin candado de evidencia. */
export async function setTaskEstado(taskId: string, status: TaskStatus): Promise<BoardTask> {
  const r = await api.patch<BoardTask>(`/tasks/${taskId}/estado`, { status })
  return r.data
}

/** Cambia el responsable de una tarea. Devuelve la tarea actualizada. */
export async function setTaskOwner(taskId: string, owner: string): Promise<BoardTask> {
  const r = await api.patch<BoardTask>(`/tasks/${taskId}`, { owner })
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
