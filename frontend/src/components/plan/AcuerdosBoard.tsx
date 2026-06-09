"use client"

import { useState } from "react"
import {
  DndContext, PointerSensor, useSensor, useSensors,
  useDraggable, useDroppable, type DragEndEvent,
} from "@dnd-kit/core"
import { Paperclip } from "lucide-react"
import { AnnualPlan, MonthlyPlan, Task, MONTH_NAMES } from "@/lib/annualPlan"

const COLUMNS: { id: Task["status"]; label: string }[] = [
  { id: "pendiente", label: "Pendiente" },
  { id: "en_progreso", label: "En proceso" },
  { id: "completada", label: "Validado" },
]
const PRIO_DOT: Record<string, string> = { alta: "bg-red-400", media: "bg-amber-400", baja: "bg-gray-300" }

type Item = { task: Task; month: MonthlyPlan }

function Card({ item, onClick }: { item: Item; onClick: () => void }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: item.task.id })
  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)`, zIndex: 50 }
    : undefined
  const t = item.task
  return (
    <div
      ref={setNodeRef} style={style} {...attributes} {...listeners}
      onClick={onClick}
      className={`bg-white border border-gray-100 rounded-xl p-3 space-y-2 cursor-grab active:cursor-grabbing ${isDragging ? "opacity-50" : ""}`}
    >
      <p className="text-sm text-black font-medium leading-snug">{t.title}</p>
      <div className="flex items-center gap-2 text-[11px] text-gray-400">
        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${PRIO_DOT[t.priority] ?? "bg-gray-300"}`} />
        <span>{MONTH_NAMES[item.month.period_month]}</span>
        {t.owner && <span className="truncate">· {t.owner}</span>}
        {t.evidence_count > 0 && (
          <span className="ml-auto inline-flex items-center gap-0.5 text-gray-500">
            <Paperclip className="h-3 w-3" />{t.evidence_count}
          </span>
        )}
      </div>
    </div>
  )
}

function Column({
  id, label, items, onTaskClick,
}: { id: Task["status"]; label: string; items: Item[]; onTaskClick: (t: Task) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id })
  return (
    <div ref={setNodeRef} className={`flex-1 min-w-0 rounded-2xl p-3 space-y-2 transition-colors ${isOver ? "bg-gray-100" : "bg-gray-50/60"}`}>
      <div className="flex items-center justify-between px-1">
        <span className="text-xs font-bold text-gray-500 uppercase tracking-wide">{label}</span>
        <span className="text-xs text-gray-400">{items.length}</span>
      </div>
      {items.map(it => (
        <Card key={it.task.id} item={it} onClick={() => onTaskClick(it.task)} />
      ))}
      {items.length === 0 && <p className="text-xs text-gray-300 px-1 py-6 text-center">—</p>}
    </div>
  )
}

export default function AcuerdosBoard({
  plan, onMoveTask, onTaskClick,
}: {
  plan: AnnualPlan
  onMoveTask: (taskId: string, status: Task["status"]) => void
  onTaskClick: (task: Task) => void
}) {
  const [warn, setWarn] = useState<string | null>(null)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  const items: Item[] = plan.months.flatMap(m =>
    m.objectives.flatMap(o => o.tasks.map(t => ({ task: t, month: m }))))

  const onDragEnd = (e: DragEndEvent) => {
    const id = String(e.active.id)
    const over = e.over ? String(e.over.id) : null
    if (!over) return
    const item = items.find(it => it.task.id === id)
    if (!item) return
    if (!COLUMNS.some(c => c.id === over)) return
    if (over === item.task.status) return
    if (over === "completada" && item.task.evidence_count === 0) {
      setWarn("Sube evidencia para validar este acuerdo (abre la tarjeta).")
      return
    }
    setWarn(null)
    onMoveTask(id, over as Task["status"])
  }

  return (
    <div className="space-y-3">
      {warn && <p className="text-xs text-red-500">{warn}</p>}
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <div className="flex gap-3 items-start">
          {COLUMNS.map(c => (
            <Column
              key={c.id} id={c.id} label={c.label}
              items={items.filter(it => it.task.status === c.id)}
              onTaskClick={onTaskClick}
            />
          ))}
        </div>
      </DndContext>
    </div>
  )
}
