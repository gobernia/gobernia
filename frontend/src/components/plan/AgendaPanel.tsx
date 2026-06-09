"use client"

import { useEffect, useState } from "react"
import { AgendaItem, getAgenda } from "@/lib/agenda"

const CHIP: Record<string, string> = {
  alto: "bg-red-100 text-red-700", alta: "bg-red-100 text-red-700",
  medio: "bg-amber-100 text-amber-700", media: "bg-amber-100 text-amber-700",
  bajo: "bg-gray-100 text-gray-500", baja: "bg-gray-100 text-gray-500",
}

export default function AgendaPanel() {
  const [items, setItems] = useState<AgendaItem[] | null>(null)

  useEffect(() => {
    let active = true
    getAgenda().then(a => { if (active) setItems(a) }).catch(() => { if (active) setItems([]) })
    return () => { active = false }
  }, [])

  if (items === null) return null
  if (items.length === 0) return null

  return (
    <div className="mb-4 rounded-2xl border border-gray-100 bg-white p-4">
      <h3 className="text-sm font-bold text-black uppercase tracking-wide mb-3">Agenda del mes</h3>
      <ol className="space-y-3">
        {items.map(i => (
          <li key={i.orden} className="flex gap-3">
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-bold flex items-center justify-center">
              {i.orden}
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-black">{i.titulo}</span>
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${CHIP[i.impacto] ?? CHIP.bajo}`}>
                  impacto {i.impacto}
                </span>
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${CHIP[i.urgencia] ?? CHIP.baja}`}>
                  urgencia {i.urgencia}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">{i.racional}</p>
              {i.evidencia.map((e, k) => (
                <p key={k} className="text-xs text-gray-400 mt-0.5">· {e}</p>
              ))}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
