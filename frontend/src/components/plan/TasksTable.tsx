"use client"

import { useEffect, useState } from "react"
import { MoreHorizontal, Paperclip, Plus, Trash2 } from "lucide-react"
import type { Objective, Task } from "@/lib/annualPlan"

const STATUS: { id: Task["status"]; label: string; cls: string }[] = [
  { id: "pendiente", label: "Pendiente", cls: "bg-gray-100 text-gray-600" },
  { id: "en_progreso", label: "En proceso", cls: "bg-amber-100 text-amber-700" },
  { id: "completada", label: "Validado", cls: "bg-green-100 text-green-700" },
]

export default function TasksTable({
  objectives, onTaskClick, onUpdateTask, onAddTask, onRenameObjective, onDeleteObjective,
}: {
  objectives: Objective[]
  onTaskClick: (t: Task) => void
  onUpdateTask: (taskId: string, patch: Partial<Task>) => void
  onAddTask: (objectiveId: string) => void
  onRenameObjective: (objectiveId: string, title: string) => void
  onDeleteObjective: (objectiveId: string) => void
}) {
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    if (!notice) return
    const t = setTimeout(() => setNotice(null), 4000)
    return () => clearTimeout(t)
  }, [notice])

  const onStatusChange = (task: Task, status: Task["status"]) => {
    if (status === task.status) return
    if (status === "completada" && task.evidence_count === 0) {
      setNotice("Sube evidencia para validar esta tarea — se abrió el detalle.")
      onTaskClick(task)
      return
    }
    onUpdateTask(task.id, { status })
  }

  if (objectives.length === 0) {
    return <p className="text-sm text-gray-400 italic">Este mes aún no tiene objetivos.</p>
  }

  return (
    <div className="space-y-5">
      {notice && (
        <p className="text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {notice}
        </p>
      )}

      {objectives.map(o => (
        <ObjectiveGroup
          key={o.id}
          objective={o}
          onTaskClick={onTaskClick}
          onUpdateTask={onUpdateTask}
          onStatusChange={onStatusChange}
          onAddTask={onAddTask}
          onRenameObjective={onRenameObjective}
          onDeleteObjective={onDeleteObjective}
        />
      ))}
    </div>
  )
}

function ObjectiveGroup({
  objective, onTaskClick, onUpdateTask, onStatusChange, onAddTask, onRenameObjective, onDeleteObjective,
}: {
  objective: Objective
  onTaskClick: (t: Task) => void
  onUpdateTask: (taskId: string, patch: Partial<Task>) => void
  onStatusChange: (t: Task, s: Task["status"]) => void
  onAddTask: (objectiveId: string) => void
  onRenameObjective: (objectiveId: string, title: string) => void
  onDeleteObjective: (objectiveId: string) => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="rounded-2xl border border-gray-100 bg-white overflow-hidden">
      <div className="flex items-center justify-between gap-2 px-4 py-2.5 border-b border-gray-100">
        <input
          defaultValue={objective.title}
          onBlur={e => {
            const v = e.target.value.trim()
            if (v && v !== objective.title) onRenameObjective(objective.id, v)
          }}
          className="text-sm font-bold text-black bg-transparent outline-none flex-1 min-w-0"
        />
        <div className="relative shrink-0">
          <button type="button" onClick={() => setMenuOpen(v => !v)}
            className="text-gray-300 hover:text-gray-500 p-1">
            <MoreHorizontal className="h-4 w-4" />
          </button>
          {menuOpen && (
            <button
              type="button"
              onClick={() => { setMenuOpen(false); onDeleteObjective(objective.id) }}
              className="absolute right-0 top-7 z-10 flex items-center gap-1.5 bg-white border border-gray-200 rounded-lg shadow-sm px-3 py-1.5 text-xs text-red-600 whitespace-nowrap"
            >
              <Trash2 className="h-3 w-3" /> Eliminar objetivo
            </button>
          )}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-gray-400">
              <th className="text-left font-medium px-4 py-2">Tarea</th>
              <th className="text-left font-medium px-2 py-2 w-40">Responsable</th>
              <th className="text-left font-medium px-2 py-2 w-36">Vence</th>
              <th className="text-left font-medium px-2 py-2 w-32">Estado</th>
              <th className="text-left font-medium px-2 py-2 w-12">
                <Paperclip className="h-3 w-3" />
              </th>
            </tr>
          </thead>
          <tbody>
            {objective.tasks.map(t => {
              const st = STATUS.find(s => s.id === t.status) ?? STATUS[0]
              return (
                <tr key={t.id} className="border-t border-gray-50 hover:bg-gray-50/60">
                  <td className="px-4 py-2">
                    <button
                      type="button"
                      onClick={() => onTaskClick(t)}
                      className="text-left text-black hover:text-[var(--gob-navy)] hover:underline"
                    >
                      {t.title}
                    </button>
                  </td>
                  <td className="px-2 py-2">
                    <input
                      defaultValue={t.owner ?? ""}
                      placeholder="➕ asignar"
                      onBlur={e => {
                        const v = e.target.value.trim()
                        if (v !== (t.owner ?? "")) onUpdateTask(t.id, { owner: v || null })
                      }}
                      className="w-full bg-transparent outline-none text-xs text-gray-700 placeholder:text-gray-300 border border-transparent focus:border-gray-200 rounded px-1.5 py-1"
                    />
                  </td>
                  <td className="px-2 py-2">
                    <input
                      type="date"
                      defaultValue={t.due_date ?? ""}
                      onChange={e => onUpdateTask(t.id, { due_date: e.target.value || null })}
                      className="bg-transparent outline-none text-xs text-gray-700 border border-transparent focus:border-gray-200 rounded px-1.5 py-1"
                    />
                  </td>
                  <td className="px-2 py-2">
                    <select
                      value={t.status}
                      onChange={e => onStatusChange(t, e.target.value as Task["status"])}
                      className={`text-xs font-medium rounded-full px-2.5 py-1 outline-none cursor-pointer appearance-none ${st.cls}`}
                    >
                      {STATUS.map(s => (
                        <option key={s.id} value={s.id}>{s.label}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-2 text-xs text-gray-400">
                    {t.evidence_count > 0 ? t.evidence_count : ""}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        onClick={() => onAddTask(objective.id)}
        className="w-full flex items-center gap-1.5 px-4 py-2 text-xs text-gray-400 hover:text-[var(--gob-navy)] border-t border-gray-50"
      >
        <Plus className="h-3.5 w-3.5" /> Agregar tarea
      </button>
    </div>
  )
}
