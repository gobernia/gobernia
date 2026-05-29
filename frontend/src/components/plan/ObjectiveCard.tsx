"use client"

import { useState } from "react"
import { Plus, Trash2, Target } from "lucide-react"
import type { Objective, Task } from "@/lib/annualPlan"
import TaskRow from "./TaskRow"

export default function ObjectiveCard({
  objective, onTaskClick, onAddTask, onRenameObjective, onDeleteObjective,
}: {
  objective: Objective
  onTaskClick: (t: Task) => void
  onAddTask: (objectiveId: string) => void
  onRenameObjective: (objectiveId: string, title: string) => void
  onDeleteObjective: (objectiveId: string) => void
}) {
  const [title, setTitle] = useState(objective.title)

  return (
    <div className="border border-gray-100 rounded-2xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          onBlur={() => title.trim() && title !== objective.title && onRenameObjective(objective.id, title.trim())}
          className="flex-1 text-sm font-bold text-black bg-transparent focus:outline-none focus:bg-gray-50 rounded px-1 -mx-1"
        />
        <button
          onClick={() => onDeleteObjective(objective.id)}
          className="text-gray-300 hover:text-red-500 transition-colors flex-shrink-0"
          aria-label="Borrar objetivo"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {objective.kpi_refs.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {objective.kpi_refs.map(k => (
            <span key={k} className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-md border border-gray-200 text-gray-600">
              <Target className="h-2.5 w-2.5" /> {k}
            </span>
          ))}
        </div>
      )}

      <div className="space-y-0.5">
        {objective.tasks.map(t => (
          <TaskRow key={t.id} task={t} onClick={() => onTaskClick(t)} />
        ))}
      </div>

      <button
        onClick={() => onAddTask(objective.id)}
        className="w-full flex items-center justify-center gap-1.5 text-xs text-gray-400 hover:text-[var(--gob-navy)] border border-dashed border-gray-200 hover:border-gray-400 rounded-lg py-2 transition-colors"
      >
        <Plus className="h-3 w-3" /> Nueva tarea
      </button>
    </div>
  )
}
