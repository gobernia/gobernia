"use client"

import { useState } from "react"
import {
  DndContext, PointerSensor, useSensor, useSensors,
  useDraggable, useDroppable, type DragEndEvent,
} from "@dnd-kit/core"
import { Paperclip } from "lucide-react"
import { Objective, Task } from "@/lib/annualPlan"

const COLUMNS: { id: Task["status"]; label: string }[] = [
  { id: "pendiente", label: "Pendiente" },
  { id: "en_progreso", label: "En proceso" },
  { id: "completada", label: "Validado" },
]
const PRIO_DOT: Record<string, string> = { alta: "bg-red-400", media: "bg-amber-400", baja: "bg-gray-300" }

function Card({ task, onClick }: { task: Task; onClick: () => void }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: task.id })
  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)`, zIndex: 50 }
    : undefined
  return (
    <div
      ref={setNodeRef} style={style} {...attributes} {...listeners}
      onClick={onClick}
      className={`bg-white border border-gray-100 rounded-xl p-3 space-y-2 cursor-grab active:cursor-grabbing ${isDragging ? "opacity-50" : ""}`}
    >
      <p className="text-sm text-black font-medium leading-snug">{task.title}</p>
      <div className="flex items-center gap-2 text-[11px] text-gray-400">
        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${PRIO_DOT[task.priority] ?? "bg-gray-300"}`} />
        {task.owner && <span className="truncate">{task.owner}</span>}
        {task.evidence_count > 0 && (
          <span className="ml-auto inline-flex items-center gap-0.5 text-gray-500">
            <Paperclip className="h-3 w-3" />{task.evidence_count}
          </span>
        )}
      </div>
    </div>
  )
}

function Column({
  id, label, tasks, onTaskClick,
}: { id: Task["status"]; label: string; tasks: Task[]; onTaskClick: (t: Task) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id })
  return (
    <div ref={setNodeRef} className={`flex-1 min-w-0 rounded-2xl p-3 space-y-2 transition-colors ${isOver ? "bg-gray-100" : "bg-gray-50/60"}`}>
      <div className="flex items-center justify-between px-1">
        <span className="text-xs font-bold text-gray-500 uppercase tracking-wide">{label}</span>
        <span className="text-xs text-gray-400">{tasks.length}</span>
      </div>
      {tasks.map(t => (
        <Card key={t.id} task={t} onClick={() => onTaskClick(t)} />
      ))}
      {tasks.length === 0 && <p className="text-xs text-gray-300 px-1 py-6 text-center">—</p>}
    </div>
  )
}

export default function MonthKanban({
  objectives, onTaskClick, onUpdateTask,
}: {
  objectives: Objective[]
  onTaskClick: (task: Task) => void
  onUpdateTask: (taskId: string, patch: Partial<Task>) => void
}) {
  const [warn, setWarn] = useState<string | null>(null)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  const tasks: Task[] = objectives.flatMap(o => o.tasks)

  const onDragEnd = (e: DragEndEvent) => {
    const id = String(e.active.id)
    const over = e.over ? String(e.over.id) : null
    if (!over) { setWarn(null); return }
    const task = tasks.find(t => t.id === id)
    if (!task) return
    if (!COLUMNS.some(c => c.id === over)) return
    if (over === task.status) return
    if (over === "completada" && task.evidence_count === 0) {
      setWarn("Sube evidencia para validar esta tarea (abre la tarjeta).")
      return
    }
    setWarn(null)
    onUpdateTask(id, { status: over as Task["status"] })
  }

  return (
    <div className="space-y-3">
      {warn && <p className="text-xs text-red-500">{warn}</p>}
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <div className="flex gap-3 items-start">
          {COLUMNS.map(c => (
            <Column
              key={c.id} id={c.id} label={c.label}
              tasks={tasks.filter(t => t.status === c.id)}
              onTaskClick={onTaskClick}
            />
          ))}
        </div>
      </DndContext>
    </div>
  )
}
