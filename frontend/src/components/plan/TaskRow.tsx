"use client"

import type { Task, TaskPriority } from "@/lib/annualPlan"
import { User, Calendar } from "lucide-react"

const PRIORITY_DOT: Record<TaskPriority, string> = {
  alta: "bg-red-500", media: "bg-amber-500", baja: "bg-emerald-500",
}

function shortDate(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(iso + "T00:00:00")
  return d.toLocaleDateString("es-MX", { day: "numeric", month: "short" })
}

export default function TaskRow({ task, onClick }: { task: Task; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-gray-50 transition-colors text-left group"
    >
      <span className={`h-2 w-2 rounded-full flex-shrink-0 ${PRIORITY_DOT[task.priority]}`} />
      <span className={`text-sm flex-1 truncate ${
        task.status === "completada" ? "line-through text-gray-400" : "text-black"
      }`}>
        {task.title}
      </span>
      {task.owner && (
        <span className="hidden sm:flex items-center gap-1 text-[11px] text-gray-400 flex-shrink-0">
          <User className="h-3 w-3" /> {task.owner}
        </span>
      )}
      {task.due_date && (
        <span className="flex items-center gap-1 text-[11px] text-gray-400 flex-shrink-0">
          <Calendar className="h-3 w-3" /> {shortDate(task.due_date)}
        </span>
      )}
    </button>
  )
}
