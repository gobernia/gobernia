"use client"

import { useEffect, useState } from "react"
import { OrdenDelDia, getOrdenDelDia } from "@/lib/ordenDelDia"
import { FREQ_LABEL } from "@/lib/boardThemes"

export default function OrdenDelDiaPanel({ monthIndex }: { monthIndex: number }) {
  const [orden, setOrden] = useState<OrdenDelDia | null>(null)

  useEffect(() => {
    let active = true
    getOrdenDelDia(monthIndex).then(o => { if (active) setOrden(o) }).catch(() => {})
    return () => { active = false }
  }, [monthIndex])

  if (!orden) return null
  if (orden.permanent_themes.length === 0 && orden.coverage_themes.length === 0) return null

  return (
    <div className="rounded-2xl border border-gray-100 bg-gray-50/60 p-5 space-y-4">
      <h3 className="text-sm font-bold text-black uppercase tracking-wide">Orden del día</h3>

      <div>
        <p className="text-xs font-medium text-gray-400 uppercase mb-1.5">Permanentes</p>
        <ul className="space-y-1">
          {orden.permanent_themes.map(t => (
            <li key={t.key} className="text-sm text-black flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--gob-navy)] flex-shrink-0" />
              {t.label}
            </li>
          ))}
        </ul>
      </div>

      {orden.coverage_themes.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-400 uppercase mb-1.5">Cobertura este mes</p>
          <ul className="space-y-1">
            {orden.coverage_themes.map(t => (
              <li key={t.key} className="text-sm text-black flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                {t.label}
                {t.every_n_sessions != null && (
                  <span className="text-xs text-gray-400">· {FREQ_LABEL[t.every_n_sessions]}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {orden.objectives.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-400 uppercase mb-1.5">Objetivos del mes</p>
          <ul className="space-y-1">
            {orden.objectives.map(o => (
              <li key={o.id} className="text-sm text-black">
                {o.title}
                {o.kpi_refs.length > 0 && (
                  <span className="text-xs text-gray-400"> · {o.kpi_refs.join(", ")}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
