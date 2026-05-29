"use client"

import type { MonthReview, Proposal, Grade } from "@/lib/annualPlan"
import { Check, ArrowRight } from "lucide-react"
import InfoHint from "@/components/ui/InfoHint"

const GRADE_STYLE: Record<Grade, { label: string; cls: string }> = {
  bien:    { label: "Vas bien",     cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  mal:     { label: "Vas mal",      cls: "bg-amber-50 text-amber-700 border-amber-200" },
  muy_mal: { label: "Vas muy mal",  cls: "bg-red-50 text-red-700 border-red-200" },
}

const PROPOSAL_LABEL: Record<Proposal["type"], string> = {
  carry_over_task: "Arrastrar tarea pendiente",
  new_objective:   "Nuevo objetivo",
  new_task:        "Nueva tarea",
}

export default function MonthReviewPanel({
  review, onApply,
}: {
  review: MonthReview
  onApply: (proposalId: string) => void
}) {
  const g = GRADE_STYLE[review.grade]
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className={`inline-flex items-center px-3 py-1.5 rounded-lg border text-sm font-bold ${g.cls}`}>
          {g.label}
        </div>
        <InfoHint text="El veredicto del consejo sobre tu mes, según el cumplimiento de tareas y el avance de tus KPIs." />
      </div>
      <p className="text-sm text-gray-600 leading-relaxed">{review.summary}</p>

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-xl border border-gray-100 py-2">
          <p className="text-lg font-bold text-black">{review.signals.completion_pct}%</p>
          <p className="text-[10px] text-gray-400">tareas completadas</p>
        </div>
        <div className="rounded-xl border border-gray-100 py-2">
          <p className="text-lg font-bold text-black">{review.signals.tasks_overdue}</p>
          <p className="text-[10px] text-gray-400">atrasadas</p>
        </div>
        <div className="rounded-xl border border-gray-100 py-2">
          <p className="text-lg font-bold text-black">{review.signals.kpis.filter(k => k.on_track).length}/{review.signals.kpis.length}</p>
          <p className="text-[10px] text-gray-400">KPIs en rumbo</p>
        </div>
      </div>

      {review.proposals.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Propuestas para el mes siguiente <InfoHint text="Cambios que el consejo sugiere para el mes siguiente; tú eliges cuáles aplicar." /></p>
          {review.proposals.map(p => (
            <div key={p.id} className="flex items-center gap-3 border border-gray-100 rounded-xl px-3 py-2.5">
              <div className="flex-1">
                <p className="text-sm text-black">
                  <span className="font-medium">{PROPOSAL_LABEL[p.type]}</span>
                  {p.title ? `: ${p.title}` : ""}
                </p>
                {p.reason && <p className="text-[11px] text-gray-400 mt-0.5">{p.reason}</p>}
              </div>
              <button
                onClick={() => onApply(p.id)}
                disabled={p.applied}
                className={`flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-colors ${
                  p.applied
                    ? "border-emerald-200 bg-emerald-50 text-emerald-600 cursor-default"
                    : "border-gray-200 text-gray-600 hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)]"
                }`}
              >
                {p.applied ? <><Check className="h-3 w-3" /> Aplicada</> : <><ArrowRight className="h-3 w-3" /> Aplicar</>}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
