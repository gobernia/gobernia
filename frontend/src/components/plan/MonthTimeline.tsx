"use client"

import type { MonthlyPlan } from "@/lib/annualPlan"
import { MONTH_NAMES } from "@/lib/annualPlan"

export default function MonthTimeline({
  months, selectedIndex, onSelect,
}: {
  months: MonthlyPlan[]
  selectedIndex: number
  onSelect: (monthIndex: number) => void
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 snap-x">
      {months.map(m => {
        const isSelected = m.month_index === selectedIndex
        const isActive = m.status === "active"
        const isDone = m.status === "done"
        return (
          <button
            key={m.id}
            onClick={() => onSelect(m.month_index)}
            className={`snap-start flex-shrink-0 w-28 text-left rounded-xl border-2 px-3 py-2.5 transition-all ${
              isSelected
                ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                : "border-gray-100 bg-white text-gray-500 hover:border-gray-300"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-medium uppercase tracking-wide opacity-70">
                Mes {m.month_index}
              </span>
              {isActive && !isSelected && (
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--gob-navy)]" />
              )}
              {isDone && !isSelected && (() => {
                const grade = (m.review as { grade?: string } | null)?.grade
                const dot = grade === "bien" ? "bg-emerald-500"
                  : grade === "mal" ? "bg-amber-500"
                  : grade === "muy_mal" ? "bg-red-500" : "bg-gray-300"
                return <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
              })()}
            </div>
            <p className={`text-sm font-bold mt-0.5 ${isSelected ? "" : "text-black"}`}>
              {MONTH_NAMES[m.period_month]}
            </p>
            <p className={`text-[10px] mt-0.5 line-clamp-1 ${isSelected ? "opacity-80" : "text-gray-400"}`}>
              {m.focus ?? "Sin foco"}
            </p>
          </button>
        )
      })}
    </div>
  )
}
