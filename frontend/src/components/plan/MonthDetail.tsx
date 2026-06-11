"use client"

import { useMemo, useState } from "react"
import { motion } from "framer-motion"
import { CheckCircle2, ChevronDown, FileText, Plus } from "lucide-react"
import type { MonthlyPlan, Task, MonthReview } from "@/lib/annualPlan"
import { MONTH_NAMES } from "@/lib/annualPlan"
import MonthReviewPanel from "./MonthReviewPanel"
import TasksTable from "./TasksTable"
import OrdenDelDiaPanel from "@/components/plan/OrdenDelDiaPanel"

export default function MonthDetail({
  month, onTaskClick, onUpdateTask, onAddTask, onRenameObjective, onDeleteObjective,
  onAddObjective, onCloseMonth, onApplyProposal,
}: {
  month: MonthlyPlan
  onTaskClick: (t: Task) => void
  onUpdateTask: (taskId: string, patch: Partial<Task>) => void
  onAddTask: (objectiveId: string) => void
  onRenameObjective: (objectiveId: string, title: string) => void
  onDeleteObjective: (objectiveId: string) => void
  onAddObjective: (monthlyPlanId: string) => void
  onCloseMonth: (monthlyPlanId: string) => void
  onApplyProposal: (monthIndex: number, proposalId: string) => void
}) {
  const [ordenOpen, setOrdenOpen] = useState(false)

  const kpis = useMemo(
    () => Array.from(new Set(month.objectives.flatMap(o => o.kpi_refs))).slice(0, 6),
    [month.objectives],
  )

  return (
    <motion.div
      key={month.id}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-5"
    >
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">
            {MONTH_NAMES[month.period_month]} {month.period_year} · Mes {month.month_index}
          </p>
          {month.focus && <h2 className="text-xl font-bold text-black mt-1">{month.focus}</h2>}
        </div>
        <button
          type="button"
          onClick={() => setOrdenOpen(v => !v)}
          className="flex items-center gap-1.5 text-xs font-medium text-[var(--gob-navy)] border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50"
        >
          <FileText className="h-3.5 w-3.5" /> Orden del día
          <ChevronDown className={`h-3.5 w-3.5 transition-transform ${ordenOpen ? "rotate-180" : ""}`} />
        </button>
      </div>

      {ordenOpen && <OrdenDelDiaPanel monthIndex={month.month_index} />}

      {kpis.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] uppercase tracking-wide text-gray-400 font-medium">KPIs:</span>
          {kpis.map(k => (
            <span key={k} className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
              {k}
            </span>
          ))}
        </div>
      )}

      {month.status === "done" && month.review && (
        <MonthReviewPanel
          review={month.review as unknown as MonthReview}
          onApply={pid => onApplyProposal(month.month_index, pid)}
        />
      )}

      <TasksTable
        objectives={month.objectives}
        onTaskClick={onTaskClick}
        onUpdateTask={onUpdateTask}
        onAddTask={onAddTask}
        onRenameObjective={onRenameObjective}
        onDeleteObjective={onDeleteObjective}
      />

      {month.status === "active" && (
        <button
          onClick={() => onCloseMonth(month.id)}
          className="w-full flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium rounded-xl py-3 hover:bg-[var(--gob-ink)] transition-colors"
        >
          <CheckCircle2 className="h-4 w-4" /> Cerrar mes y revisar
        </button>
      )}

      <button
        onClick={() => onAddObjective(month.id)}
        className="w-full flex items-center justify-center gap-1.5 text-xs font-medium text-gray-500 hover:text-[var(--gob-navy)] border border-dashed border-gray-200 hover:border-gray-400 rounded-xl py-2.5 transition-colors"
      >
        <Plus className="h-3.5 w-3.5" /> Agregar objetivo
      </button>
    </motion.div>
  )
}
