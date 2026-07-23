import api from "@/lib/api"

/**
 * El tablero del plan mensual — la vista tipo Monday del Centro de operaciones.
 *
 * Alimenta el `<TableroPlan/>` del consejo: cada mes es un grupo con sus tareas,
 * y el estado de cada tarea se cambia sin candado (a diferencia del Plan).
 */

export type TaskStatus = "pendiente" | "en_progreso" | "completada"
export type TaskPriority = "alta" | "media" | "baja"

export interface BoardTask {
  id: string
  title: string
  owner: string | null
  status: TaskStatus
  priority: TaskPriority
  due_date: string | null
  objetivo: string | null
}

export interface BoardMes {
  month_index: number
  period_year: number
  period_month: number
  label: string
  es_mes_actual: boolean
  tareas: BoardTask[]
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
