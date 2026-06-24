import api from "@/lib/api"

export type TaskStatus = "pendiente" | "en_progreso" | "completada"
export type TaskPriority = "alta" | "media" | "baja"
export type PlanStatus = "generating" | "active" | "failed" | "completed"

export interface Milestone {
  type: "trimestral" | "semestral" | "anual"
  year: number
  period: number
  title: string
  target: string
  kpi_ref: string | null
}

export interface ExplicacionTarea {
  tiempo: string
  dificultad: string
  que_es: string
  como: string[]
}

export interface Task {
  id: string
  plan_id: string | null
  objective_id: string | null
  kpi_ref: string | null
  title: string
  description: string | null
  source_agent: string | null
  status: TaskStatus
  priority: TaskPriority
  owner: string | null
  due_date: string | null
  tags: string[]
  order_index: number
  created_at: string
  updated_at: string
  evidence_count: number
  required_doc: string | null
  explicacion: ExplicacionTarea | null
}

export interface Objective {
  id: string
  title: string
  description: string | null
  kpi_refs: string[]
  order_index: number
  tasks: Task[]
}

export interface MonthlyPlan {
  id: string
  month_index: number
  period_year: number
  period_month: number
  focus: string | null
  status: "locked" | "active" | "done"
  review: Record<string, unknown> | null
  objectives: Objective[]
}

export interface AnnualPlan {
  id: string
  title: string
  start_date: string
  status: PlanStatus
  diagnostico_summary: string | null
  genesis_session_id: string | null
  months: MonthlyPlan[]
  horizon_years: number
  milestones: { items: Milestone[] } | null
}

export interface AnnualPlanStatus {
  status: PlanStatus
  active_month_index: number | null
}

export const MONTH_NAMES = [
  "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

export async function getAnnualPlan(): Promise<AnnualPlan> {
  const r = await api.get<AnnualPlan>("/annual-plan")
  return r.data
}

export async function getAnnualPlanStatus(): Promise<AnnualPlanStatus> {
  const r = await api.get<AnnualPlanStatus>("/annual-plan/status")
  return r.data
}

export async function generateAnnualPlan(horizonYears: number = 3): Promise<AnnualPlanStatus> {
  const r = await api.post<AnnualPlanStatus>("/annual-plan/generate", { horizon_years: horizonYears })
  return r.data
}

export async function createObjective(body: {
  monthly_plan_id: string
  title: string
  description?: string | null
  kpi_refs?: string[]
}): Promise<Objective> {
  const r = await api.post<Objective>("/annual-plan/objectives", body)
  return r.data
}

export async function updateObjective(
  id: string,
  patch: Partial<Pick<Objective, "title" | "description" | "kpi_refs" | "order_index">>,
): Promise<Objective> {
  const r = await api.patch<Objective>(`/annual-plan/objectives/${id}`, patch)
  return r.data
}

export async function deleteObjective(id: string): Promise<void> {
  await api.delete(`/annual-plan/objectives/${id}`)
}

export async function createTask(body: {
  objective_id: string
  title: string
  description?: string | null
  status?: TaskStatus
  priority?: TaskPriority
  owner?: string | null
  due_date?: string | null
  kpi_ref?: string | null
  tags?: string[]
}): Promise<Task> {
  const r = await api.post<Task>("/annual-plan/tasks", body)
  return r.data
}

export async function updateTask(id: string, patch: Partial<Task>): Promise<Task> {
  const r = await api.patch<Task>(`/tasks/${id}`, patch)
  return r.data
}

export async function deleteTask(id: string): Promise<void> {
  await api.delete(`/tasks/${id}`)
}

export async function getTaskExplicacion(taskId: string): Promise<ExplicacionTarea> {
  const r = await api.post<ExplicacionTarea>(`/tasks/${taskId}/explicacion`)
  return r.data
}

export interface AdaptacionTarea {
  nueva_tarea: string
  descripcion: string
  por_que: string
}

export async function adaptTask(taskId: string, feedback: string): Promise<AdaptacionTarea> {
  const r = await api.post<AdaptacionTarea>(`/tasks/${taskId}/adaptar`, { feedback })
  return r.data
}

export type Grade = "bien" | "mal" | "muy_mal"

export interface ReviewSignals {
  tasks_total: number
  tasks_completed: number
  tasks_overdue: number
  completion_pct: number
  kpis: { label: string; value: number | null; target: number | null; unit: string | null; on_track: boolean | null }[]
}

export interface Proposal {
  id: string
  type: "carry_over_task" | "new_objective" | "new_task"
  applied: boolean
  reason?: string
  task_id?: string
  title?: string
  description?: string | null
  kpi_refs?: string[]
  objective_id?: string
  owner?: string | null
  priority?: TaskPriority
  kpi_ref?: string | null
}

export interface MonthReview {
  grade: Grade
  closed_at?: string
  summary: string
  by_agent: Record<string, string>
  signals: ReviewSignals
  proposals: Proposal[]
}

export async function closeMonth(monthIndex: number, kpis: Record<string, number>) {
  const r = await api.post<{ month_index: number; active_month_index: number; grade: Grade }>(
    `/annual-plan/months/${monthIndex}/close`, { kpis },
  )
  return r.data
}

export async function applyProposal(monthIndex: number, proposalId: string): Promise<MonthReview> {
  const r = await api.post<MonthReview>(
    `/annual-plan/months/${monthIndex}/apply-proposal`, { proposal_id: proposalId },
  )
  return r.data
}
