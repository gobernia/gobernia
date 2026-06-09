"use client"

import { useEffect, useState } from "react"
import { AgendaOut, getAgenda, convocarChair } from "@/lib/agenda"

const CHIP: Record<string, string> = {
  alto: "bg-red-100 text-red-700", alta: "bg-red-100 text-red-700",
  medio: "bg-amber-100 text-amber-700", media: "bg-amber-100 text-amber-700",
  bajo: "bg-gray-100 text-gray-500", baja: "bg-gray-100 text-gray-500",
}

export default function AgendaPanel() {
  const [data, setData] = useState<AgendaOut | null>(null)
  const [convocando, setConvocando] = useState(false)

  useEffect(() => {
    let active = true
    getAgenda().then(d => { if (active) setData(d) }).catch(() => { if (active) setData(null) })
    return () => { active = false }
  }, [])

  const onConvocar = async () => {
    setConvocando(true)
    try { setData(await convocarChair()) } catch { /* noop */ } finally { setConvocando(false) }
  }

  if (data === null) return null
  if (data.items.length === 0) {
    return (
      <div className="mb-4 rounded-2xl border border-gray-100 bg-white p-4">
        <h3 className="text-sm font-bold text-black uppercase tracking-wide mb-1">Agenda del mes</h3>
        <p className="text-sm text-gray-400">Sin temas priorizados este mes.</p>
      </div>
    )
  }

  return (
    <div className="mb-4 rounded-2xl border border-gray-100 bg-white p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-black uppercase tracking-wide">Agenda del mes</h3>
        <button
          type="button"
          onClick={onConvocar}
          disabled={convocando}
          className="text-xs font-medium text-[var(--gob-navy)] hover:underline disabled:opacity-50"
        >
          {convocando ? "El Chair está revisando…" : (data.curada ? "Actualizar con el Chair" : "Convocar al Chair")}
        </button>
      </div>

      {data.curada && data.carta && (
        <p className="text-sm text-gray-600 italic border-l-2 border-[var(--gob-navy)] pl-3 mb-3">
          {data.carta}
        </p>
      )}

      <ol className="space-y-3">
        {data.items.map(i => (
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
