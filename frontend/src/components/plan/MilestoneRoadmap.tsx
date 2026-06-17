"use client"

import type { AnnualPlan } from "@/lib/annualPlan"

const TYPE_LABEL: Record<string, string> = { trimestral: "Trimestre", semestral: "Semestre", anual: "Año" }

export default function MilestoneRoadmap({ milestones }: { milestones: AnnualPlan["milestones"] }) {
  const items = milestones?.items ?? []
  if (items.length === 0) return null
  const years = Array.from(new Set(items.map(m => m.year))).sort((a, b) => a - b)
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Roadmap estratégico</p>
        <h2 className="text-xl font-bold text-black tracking-tight">Tus hitos</h2>
      </div>
      <div className="space-y-5">
        {years.map(year => (
          <div key={year} className="space-y-2">
            <p className="text-[10px] uppercase tracking-wide text-gray-400 font-medium">Año {year}</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {items.filter(m => m.year === year).map((m, i) => (
                <div key={i}
                  className={`rounded-xl border p-3 space-y-1 ${m.type === "anual" ? "border-[var(--gob-navy)] bg-[var(--gob-navy)]/[0.03]" : "border-gray-100"}`}>
                  <p className="text-[10px] uppercase tracking-wide text-gray-400 font-medium">
                    {TYPE_LABEL[m.type] ?? m.type}{m.type !== "anual" ? ` ${m.period}` : ""}
                  </p>
                  <p className="text-sm font-medium text-black leading-snug">{m.title}</p>
                  {m.target && <p className="text-xs text-gray-500 leading-snug">{m.target}</p>}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
