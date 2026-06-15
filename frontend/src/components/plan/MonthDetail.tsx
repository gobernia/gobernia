"use client"

import { useMemo, useState } from "react"
import { motion } from "framer-motion"
import { CheckCircle2, ChevronDown } from "lucide-react"
import type { MonthlyPlan, Task, MonthReview } from "@/lib/annualPlan"
import { MONTH_NAMES } from "@/lib/annualPlan"
import MonthReviewPanel from "./MonthReviewPanel"
import MonthKanban from "./MonthKanban"
import OrdenDelDiaPanel from "@/components/plan/OrdenDelDiaPanel"

export default function MonthDetail({
  month, onTaskClick, onUpdateTask, onCloseMonth, onApplyProposal,
}: {
  month: MonthlyPlan
  onTaskClick: (t: Task) => void
  onUpdateTask: (taskId: string, patch: Partial<Task>) => void
  onCloseMonth: (monthlyPlanId: string) => void
  onApplyProposal: (monthIndex: number, proposalId: string) => void
}) {
  const [ordenOpen, setOrdenOpen] = useState(true)

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
      <div>
        <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">
          {MONTH_NAMES[month.period_month]} {month.period_year} · Mes {month.month_index}
        </p>
        {month.focus && <h2 className="text-xl font-bold text-black mt-1">{month.focus}</h2>}
      </div>

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

      <MonthKanban
        objectives={month.objectives}
        onTaskClick={onTaskClick}
        onUpdateTask={onUpdateTask}
      />

      {/* Orden del día — legible, expandido por defecto, debajo de las tareas */}
      <section className="border border-gray-100 rounded-2xl overflow-hidden">
        <button
          type="button"
          onClick={() => setOrdenOpen(v => !v)}
          className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50"
        >
          <span className="text-sm font-bold text-black">Orden del día</span>
          <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${ordenOpen ? "rotate-180" : ""}`} />
        </button>
        {ordenOpen && (
          <div className="px-4 pb-4 border-t border-gray-100 pt-3">
            <OrdenDelDiaPanel monthIndex={month.month_index} />
          </div>
        )}
      </section>

      {month.status === "active" && (
        <button
          onClick={() => onCloseMonth(month.id)}
          className="w-full flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium rounded-xl py-3 hover:bg-[var(--gob-ink)] transition-colors"
        >
          <CheckCircle2 className="h-4 w-4" /> Cerrar mes y revisar
        </button>
      )}
    </motion.div>
  )
}
