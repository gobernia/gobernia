"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
  type DragOverEvent,
} from "@dnd-kit/core"
import {
  SortableContext,
  useSortable,
  arrayMove,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import {
  ArrowLeft, Loader2, Plus, Trash2, X, Sparkles,
  Calendar, User, Tag, AlertCircle,
} from "lucide-react"
import api from "@/lib/api"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

type Status = "pendiente" | "en_progreso" | "completada"
type Priority = "alta" | "media" | "baja"

interface Task {
  id: string
  plan_id: string
  title: string
  description: string | null
  source_agent: string | null
  status: Status
  priority: Priority
  owner: string | null
  due_date: string | null
  tags: string[]
  order_index: number
  created_at: string
  updated_at: string
}

interface Plan {
  id: string
  board_session_id: string
  title: string
  created_at: string
  updated_at: string
  tasks: Task[]
}

const COLUMNS: { id: Status; label: string; hint: string }[] = [
  { id: "pendiente",   label: "Por hacer",     hint: "Tareas sin empezar" },
  { id: "en_progreso", label: "En progreso",   hint: "Trabajo activo" },
  { id: "completada",  label: "Completadas",   hint: "Listo" },
]

const PRIORITY_STYLES: Record<Priority, { bg: string; text: string; border: string; label: string }> = {
  alta:  { bg: "bg-red-50",    text: "text-red-700",    border: "border-red-200",    label: "Alta" },
  media: { bg: "bg-amber-50",  text: "text-amber-700",  border: "border-amber-200",  label: "Media" },
  baja:  { bg: "bg-emerald-50",text: "text-emerald-700",border: "border-emerald-200",label: "Baja" },
}

const AGENT_COLORS: Record<string, string> = {
  CFO:     "bg-blue-50 text-blue-700 border-blue-200",
  CSO:     "bg-purple-50 text-purple-700 border-purple-200",
  CRO:     "bg-orange-50 text-orange-700 border-orange-200",
  Auditor: "bg-slate-100 text-slate-700 border-slate-300",
}

function shortDate(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(iso + "T00:00:00")
  return d.toLocaleDateString("es-MX", { day: "numeric", month: "short" })
}

// ── Card ──────────────────────────────────────────────────────────

function TaskCard({
  task, onClick, isDragging,
}: { task: Task; onClick: () => void; isDragging?: boolean }) {
  const prio = PRIORITY_STYLES[task.priority]
  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-xl border border-gray-200 hover:border-gray-400 p-3.5 space-y-2.5 cursor-pointer transition-colors shadow-sm ${
        isDragging ? "shadow-lg opacity-90" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className={`text-sm font-medium text-black leading-snug flex-1 ${
          task.status === "completada" ? "line-through text-gray-400" : ""
        }`}>
          {task.title}
        </p>
      </div>

      {task.description && (
        <p className="text-xs text-gray-500 leading-relaxed line-clamp-2">
          {task.description}
        </p>
      )}

      <div className="flex items-center flex-wrap gap-1.5">
        <span className={`inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-md border ${prio.bg} ${prio.text} ${prio.border}`}>
          {prio.label}
        </span>
        {task.source_agent && (
          <span className={`inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-md border ${AGENT_COLORS[task.source_agent] ?? "bg-gray-50 text-gray-600 border-gray-200"}`}>
            {task.source_agent}
          </span>
        )}
        {task.tags.slice(0, 2).map(t => (
          <span key={t} className="inline-flex items-center text-[10px] text-gray-500 bg-gray-50 px-1.5 py-0.5 rounded">
            {t}
          </span>
        ))}
      </div>

      {(task.owner || task.due_date) && (
        <div className="flex items-center gap-3 pt-1 text-[11px] text-gray-400">
          {task.owner && (
            <div className="flex items-center gap-1 truncate">
              <User className="h-3 w-3 flex-shrink-0" />
              <span className="truncate">{task.owner}</span>
            </div>
          )}
          {task.due_date && (
            <div className="flex items-center gap-1 flex-shrink-0">
              <Calendar className="h-3 w-3" />
              {shortDate(task.due_date)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SortableTaskCard({ task, onClick }: { task: Task; onClick: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: task.id,
  })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }
  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <TaskCard task={task} onClick={onClick} />
    </div>
  )
}

// ── Column ────────────────────────────────────────────────────────

function Column({
  status, label, hint, tasks, onTaskClick, onAddClick,
}: {
  status: Status
  label: string
  hint: string
  tasks: Task[]
  onTaskClick: (t: Task) => void
  onAddClick: () => void
}) {
  return (
    <div className="bg-gray-50 rounded-2xl p-3 flex flex-col min-h-[300px]">
      <div className="flex items-center justify-between px-1 mb-3">
        <div>
          <p className="text-xs font-bold text-black">{label}</p>
          <p className="text-[10px] text-gray-400 mt-0.5">{hint}</p>
        </div>
        <span className="text-[11px] font-semibold text-gray-400 bg-white border border-gray-200 rounded-full px-2 py-0.5">
          {tasks.length}
        </span>
      </div>

      <SortableContext id={status} items={tasks.map(t => t.id)} strategy={verticalListSortingStrategy}>
        <div className="flex-1 space-y-2 min-h-[80px]">
          {tasks.map(t => (
            <SortableTaskCard key={t.id} task={t} onClick={() => onTaskClick(t)} />
          ))}
        </div>
      </SortableContext>

      <button
        onClick={onAddClick}
        className="mt-2 w-full flex items-center justify-center gap-1.5 text-xs text-gray-400 hover:text-black border border-dashed border-gray-200 hover:border-gray-400 rounded-xl py-2 transition-colors"
      >
        <Plus className="h-3 w-3" />
        Nueva tarea
      </button>
    </div>
  )
}

// ── Task editor drawer ────────────────────────────────────────────

function TaskEditor({
  task, onClose, onUpdate, onDelete,
}: {
  task: Task
  onClose: () => void
  onUpdate: (updates: Partial<Task>) => void
  onDelete: () => void
}) {
  const [local, setLocal] = useState<Task>(task)
  useEffect(() => setLocal(task), [task])

  const save = (patch: Partial<Task>) => {
    setLocal(prev => ({ ...prev, ...patch }))
    onUpdate(patch)
  }

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />
      <motion.div
        initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 40 }}
        transition={{ duration: 0.3, ease: EASE }}
        className="fixed z-50 inset-y-0 right-0 w-full sm:w-[480px] bg-white shadow-2xl overflow-y-auto"
      >
        <div className="sticky top-0 z-10 bg-white border-b border-gray-100 px-6 h-14 flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-widest">Tarea</span>
          <button onClick={onClose} className="text-gray-400 hover:text-black transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Title */}
          <textarea
            value={local.title}
            onChange={e => setLocal(p => ({ ...p, title: e.target.value }))}
            onBlur={() => local.title !== task.title && save({ title: local.title })}
            rows={2}
            className="w-full text-lg font-bold text-black resize-none focus:outline-none placeholder:text-gray-300"
            placeholder="Título de la tarea"
          />

          {/* Status */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase">Estado</label>
            <div className="flex gap-1.5">
              {COLUMNS.map(c => (
                <button
                  key={c.id}
                  onClick={() => save({ status: c.id })}
                  className={`flex-1 text-xs font-medium py-2 rounded-lg border-2 transition-all duration-100 ${
                    local.status === c.id
                      ? "border-black bg-black text-white"
                      : "border-gray-100 text-gray-500 hover:border-gray-300"
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          {/* Priority */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase">Prioridad</label>
            <div className="flex gap-1.5">
              {(["alta", "media", "baja"] as Priority[]).map(p => (
                <button
                  key={p}
                  onClick={() => save({ priority: p })}
                  className={`flex-1 text-xs font-medium py-2 rounded-lg border-2 transition-all duration-100 ${
                    local.priority === p
                      ? `${PRIORITY_STYLES[p].border} ${PRIORITY_STYLES[p].bg} ${PRIORITY_STYLES[p].text}`
                      : "border-gray-100 text-gray-500 hover:border-gray-300"
                  }`}
                >
                  {PRIORITY_STYLES[p].label}
                </button>
              ))}
            </div>
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase">Descripción</label>
            <textarea
              value={local.description ?? ""}
              onChange={e => setLocal(p => ({ ...p, description: e.target.value }))}
              onBlur={() => local.description !== task.description && save({ description: local.description })}
              rows={4}
              placeholder="Detalles, contexto, criterios de éxito…"
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-black resize-none"
            />
          </div>

          {/* Owner */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase flex items-center gap-1.5">
              <User className="h-3 w-3" /> Responsable
            </label>
            <input
              value={local.owner ?? ""}
              onChange={e => setLocal(p => ({ ...p, owner: e.target.value }))}
              onBlur={() => local.owner !== task.owner && save({ owner: local.owner || null })}
              placeholder="Director General, CFO, Consejo..."
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-black"
            />
          </div>

          {/* Due date */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase flex items-center gap-1.5">
              <Calendar className="h-3 w-3" /> Fecha límite
            </label>
            <input
              type="date"
              value={local.due_date ?? ""}
              onChange={e => save({ due_date: e.target.value || null })}
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-black"
            />
          </div>

          {/* Tags */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase flex items-center gap-1.5">
              <Tag className="h-3 w-3" /> Etiquetas
            </label>
            <input
              value={local.tags.join(", ")}
              onChange={e => setLocal(p => ({ ...p, tags: e.target.value.split(",").map(s => s.trim()).filter(Boolean) }))}
              onBlur={() => save({ tags: local.tags })}
              placeholder="compliance, liquidez, talento"
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-black"
            />
          </div>

          {local.source_agent && (
            <div className="border-t border-gray-100 pt-4 text-[11px] text-gray-400">
              Tarea generada por el agente <span className="font-semibold text-gray-600">{local.source_agent}</span>
            </div>
          )}

          {/* Delete */}
          <button
            onClick={onDelete}
            className="w-full flex items-center justify-center gap-2 text-xs font-medium text-red-500 hover:text-red-700 border border-red-100 hover:border-red-300 rounded-xl py-2.5 transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Borrar tarea
          </button>
        </div>
      </motion.div>
    </>
  )
}

// ── Page ──────────────────────────────────────────────────────────

export default function PlanPage() {
  const router = useRouter()
  const { id } = useParams<{ id: string }>()
  const [plan, setPlan] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [openTask, setOpenTask] = useState<Task | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  )

  const loadPlan = useCallback(async () => {
    try {
      const r = await api.get(`/board-sessions/${id}/plan`)
      setPlan(r.data)
      setError(null)
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        setPlan(null)  // no plan yet
      } else {
        setError("No se pudo cargar el plan.")
      }
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { loadPlan() }, [loadPlan])

  const generate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const r = await api.post(`/board-sessions/${id}/plan`)
      setPlan(r.data.plan)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "No se pudo generar el plan.")
    } finally {
      setGenerating(false)
    }
  }

  const updateTask = async (taskId: string, patch: Partial<Task>) => {
    // Optimistic update
    setPlan(p => p ? { ...p, tasks: p.tasks.map(t => t.id === taskId ? { ...t, ...patch } : t) } : p)
    if (openTask?.id === taskId) {
      setOpenTask(prev => prev ? { ...prev, ...patch } : prev)
    }
    try {
      await api.patch(`/tasks/${taskId}`, patch)
    } catch {
      loadPlan()  // revert by reloading
    }
  }

  const createTask = async (status: Status) => {
    if (!plan) return
    try {
      const r = await api.post(`/plans/${plan.id}/tasks`, {
        title: "Nueva tarea",
        status,
        priority: "media",
      })
      setPlan(p => p ? { ...p, tasks: [...p.tasks, r.data] } : p)
      setOpenTask(r.data)
    } catch {
      setError("No se pudo crear la tarea.")
    }
  }

  const deleteTask = async (taskId: string) => {
    setOpenTask(null)
    setPlan(p => p ? { ...p, tasks: p.tasks.filter(t => t.id !== taskId) } : p)
    try {
      await api.delete(`/tasks/${taskId}`)
    } catch {
      loadPlan()
    }
  }

  // ── DnD handlers ─────────────────────────────────
  const handleDragStart = (e: DragStartEvent) => setActiveId(String(e.active.id))

  const findContainer = (taskId: string): Status | null => {
    if (!plan) return null
    const t = plan.tasks.find(x => x.id === taskId)
    return t ? t.status : null
  }

  const handleDragOver = (e: DragOverEvent) => {
    if (!plan) return
    const activeId = String(e.active.id)
    const overId = String(e.over?.id ?? "")
    if (!overId) return

    // overId could be a column id (status) or a task id
    const isColumn = COLUMNS.some(c => c.id === overId)
    const activeContainer = findContainer(activeId)
    const overContainer = isColumn ? (overId as Status) : findContainer(overId)
    if (!activeContainer || !overContainer || activeContainer === overContainer) return

    setPlan(p => {
      if (!p) return p
      return {
        ...p,
        tasks: p.tasks.map(t => t.id === activeId ? { ...t, status: overContainer } : t),
      }
    })
  }

  const handleDragEnd = (e: DragEndEvent) => {
    setActiveId(null)
    if (!plan) return
    const activeId = String(e.active.id)
    const overId = String(e.over?.id ?? "")
    if (!overId) return

    const isColumn = COLUMNS.some(c => c.id === overId)
    const newStatus: Status = isColumn ? (overId as Status) : findContainer(overId)!
    const originalStatus = plan.tasks.find(t => t.id === activeId)?.status

    // Persist status change if it moved column
    if (originalStatus !== newStatus) {
      updateTask(activeId, { status: newStatus })
    } else if (activeId !== overId && !isColumn) {
      // Reorder inside same column
      const columnTasks = plan.tasks.filter(t => t.status === newStatus)
      const oldIdx = columnTasks.findIndex(t => t.id === activeId)
      const newIdx = columnTasks.findIndex(t => t.id === overId)
      const reordered = arrayMove(columnTasks, oldIdx, newIdx)
      setPlan(p => {
        if (!p) return p
        const otherTasks = p.tasks.filter(t => t.status !== newStatus)
        const updated = reordered.map((t, i) => ({ ...t, order_index: i }))
        return { ...p, tasks: [...otherTasks, ...updated] }
      })
      // Persist new order_index for moved task
      const movedTask = reordered.find(t => t.id === activeId)
      if (movedTask) {
        api.patch(`/tasks/${activeId}`, { order_index: reordered.indexOf(movedTask) }).catch(() => {})
      }
    }
  }

  // ── Render ───────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-dvh bg-white flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-gray-300" />
      </div>
    )
  }

  const tasksByStatus = (s: Status) =>
    (plan?.tasks ?? [])
      .filter(t => t.status === s)
      .sort((a, b) => a.order_index - b.order_index)

  const activeTask = activeId ? plan?.tasks.find(t => t.id === activeId) : null

  return (
    <div className="min-h-dvh bg-white text-black font-sans antialiased">
      {/* Navbar */}
      <header className="fixed top-0 inset-x-0 z-40 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <button
            onClick={() => router.push(`/dashboard/sesion/${id}`)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-black transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Volver a la sesión
          </button>
          {plan && (
            <button
              onClick={generate}
              disabled={generating}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-black transition-colors disabled:opacity-50"
            >
              {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              Regenerar plan
            </button>
          )}
        </div>
      </header>

      <main className="pt-14">
        <div className="max-w-7xl mx-auto px-6 py-10 space-y-8">

          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE }}
            className="space-y-1"
          >
            <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase">Plan de acción</p>
            <h1 className="text-3xl font-bold text-black tracking-tight">
              {plan?.title ?? "Sin plan aún"}
            </h1>
            {plan && (
              <p className="text-sm text-gray-500 mt-1">
                {plan.tasks.length} tareas · arrástralas entre columnas para cambiar su estado
              </p>
            )}
          </motion.div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
              <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {!plan ? (
            <div className="border border-gray-100 rounded-2xl p-14 flex flex-col items-center text-center space-y-6">
              <div className="w-14 h-14 rounded-2xl border-2 border-gray-100 flex items-center justify-center">
                <Sparkles className="h-5 w-5 text-gray-300" />
              </div>
              <div className="space-y-2 max-w-md">
                <p className="text-base font-semibold text-black">Genera el plan a partir del análisis</p>
                <p className="text-sm text-gray-500 leading-relaxed">
                  Convertiremos los hallazgos y recomendaciones de los 4 agentes en tareas
                  con responsable, prioridad y plazo. Después puedes editarlas, moverlas
                  entre columnas o agregar más manualmente.
                </p>
              </div>
              <button
                onClick={generate}
                disabled={generating}
                className="inline-flex items-center gap-2 bg-black text-white text-sm font-medium px-6 py-3 rounded-xl hover:bg-gray-900 transition-colors disabled:opacity-60"
              >
                {generating ? <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generando…
                </> : <>
                  <Sparkles className="h-4 w-4" />
                  Generar plan ahora
                </>}
              </button>
            </div>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCorners}
              onDragStart={handleDragStart}
              onDragOver={handleDragOver}
              onDragEnd={handleDragEnd}
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {COLUMNS.map(c => (
                  <Column
                    key={c.id}
                    status={c.id}
                    label={c.label}
                    hint={c.hint}
                    tasks={tasksByStatus(c.id)}
                    onTaskClick={setOpenTask}
                    onAddClick={() => createTask(c.id)}
                  />
                ))}
              </div>

              <DragOverlay>
                {activeTask ? <TaskCard task={activeTask} onClick={() => {}} isDragging /> : null}
              </DragOverlay>
            </DndContext>
          )}

        </div>
      </main>

      <AnimatePresence>
        {openTask && (
          <TaskEditor
            task={openTask}
            onClose={() => setOpenTask(null)}
            onUpdate={patch => updateTask(openTask.id, patch)}
            onDelete={() => deleteTask(openTask.id)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
