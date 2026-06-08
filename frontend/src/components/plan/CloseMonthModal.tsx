"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { X, Loader2 } from "lucide-react"
import AgentsCollaboration from "@/components/plan/AgentsCollaboration"
import type { MonthlyPlan } from "@/lib/annualPlan"
import { formatNumberInput, parseNumberInput } from "@/lib/format"

export default function CloseMonthModal({
  month, running, onClose, onSubmit,
}: {
  month: MonthlyPlan
  running: boolean
  onClose: () => void
  onSubmit: (kpis: Record<string, number>) => void
}) {
  const kpiLabels = Array.from(new Set(month.objectives.flatMap(o => o.kpi_refs)))
  const [values, setValues] = useState<Record<string, string>>({})

  const submit = () => {
    const kpis: Record<string, number> = {}
    for (const [k, v] of Object.entries(values)) {
      const n = parseFloat(v)
      if (!Number.isNaN(n)) kpis[k] = n
    }
    onSubmit(kpis)
  }

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm" onClick={running ? undefined : onClose}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
        className="fixed z-50 inset-0 m-auto h-fit max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white shadow-2xl"
      >
        {running ? (
          <div className="p-10 flex flex-col items-center gap-8">
            <p className="text-sm font-medium text-black">El consejo está revisando tu mes…</p>
            <AgentsCollaboration caption="Los agentes evalúan tu avance y el Challenger cuestiona el resultado antes de darte el veredicto." />
          </div>
        ) : (
          <div className="p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-black">Cerrar mes y revisar</h2>
              <button onClick={onClose} className="text-gray-400 hover:text-[var(--gob-navy)]"><X className="h-4 w-4" /></button>
            </div>
            <p className="text-sm text-gray-500 leading-relaxed">
              Ingresa los valores actuales de tus KPIs. El consejo calificará el mes y propondrá ajustes al siguiente.
            </p>
            {kpiLabels.length === 0 ? (
              <p className="text-sm text-gray-400 italic">Este mes no tiene KPIs asociados; el consejo evaluará por el avance de tareas.</p>
            ) : (
              <div className="space-y-3">
                {kpiLabels.map(label => (
                  <div key={label} className="space-y-1">
                    <label className="text-xs font-medium text-gray-600">{label}</label>
                    <input
                      type="text" inputMode="decimal"
                      value={formatNumberInput(values[label] ?? "")}
                      onChange={e => setValues(v => ({ ...v, [label]: parseNumberInput(e.target.value) }))}
                      placeholder="Valor actual"
                      className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)]"
                    />
                  </div>
                ))}
              </div>
            )}
            <button
              onClick={submit}
              className="w-full flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
            >
              <Loader2 className="h-4 w-4 hidden" /> Cerrar mes y pedir revisión
            </button>
          </div>
        )}
      </motion.div>
    </>
  )
}
