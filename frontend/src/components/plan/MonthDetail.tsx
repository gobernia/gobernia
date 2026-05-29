"use client"

import { motion } from "framer-motion"
import { Plus, CheckCircle2 } from "lucide-react"
import type { MonthlyPlan, Task, MonthReview } from "@/lib/annualPlan"
import { MONTH_NAMES } from "@/lib/annualPlan"
import ObjectiveCard from "./ObjectiveCard"
import MonthReviewPanel from "./MonthReviewPanel"

export default function MonthDetail({
  month, onTaskClick, onAddTask, onRenameObjective, onDeleteObjective, onAddObjective,
  onCloseMonth, onApplyProposal,
}: {
  month: MonthlyPlan
  onTaskClick: (t: Task) => void
  onAddTask: (objectiveId: string) => void
  onRenameObjective: (objectiveId: string, title: string) => void
  onDeleteObjective: (objectiveId: string) => void
  onAddObjective: (monthlyPlanId: string) => void
  onCloseMonth: (monthlyPlanId: string) => void
  onApplyProposal: (monthIndex: number, proposalId: string) => void
}) {
  return (
    <motion.div
      key={month.id}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-5"
    >
      <div>
        <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">
          {MONTH_NAMES[month.period_month]} {month.period_year} · Mes {month.month_index}
        </p>
        {month.focus && <h2 className="text-xl font-bold text-black mt-1">{month.focus}</h2>}
      </div>

      {month.status === "done" && month.review && (
        <MonthReviewPanel
          review={month.review as unknown as MonthReview}
          onApply={pid => onApplyProposal(month.month_index, pid)}
        />
      )}

      {month.objectives.length === 0 ? (
        <p className="text-sm text-gray-400 italic">Este mes aún no tiene objetivos.</p>
      ) : (
        <div className="space-y-3">
          {month.objectives.map(o => (
            <ObjectiveCard
              key={o.id}
              objective={o}
              onTaskClick={onTaskClick}
              onAddTask={onAddTask}
              onRenameObjective={onRenameObjective}
              onDeleteObjective={onDeleteObjective}
            />
          ))}
        </div>
      )}

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
