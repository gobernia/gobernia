"use client"

import { useEffect, useState } from "react"
import { Compromiso, getCompromisos, patchCompromiso } from "@/lib/pm"

const NUDGE: Record<string, { label: string; cls: string }> = {
  al_dia: { label: "Al día", cls: "bg-gray-100 text-gray-500" },
  recordatorio: { label: "Recordatorio (+7)", cls: "bg-amber-100 text-amber-700" },
  sin_avance_amarillo: { label: "Sin avance (+14)", cls: "bg-amber-100 text-amber-700" },
  sin_avance_rojo: { label: "Sin avance (+21)", cls: "bg-red-100 text-red-700" },
  vencido: { label: "Vencido", cls: "bg-red-100 text-red-700" },
  completado: { label: "Completado", cls: "bg-green-100 text-green-700" },
}

export default function CompromisosBoard() {
  const [items, setItems] = useState<Compromiso[] | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getCompromisos().then(d => { if (active) setItems(d) }).catch(() => { if (active) setItems([]) })
    return () => { active = false }
  }, [])

  const copyLink = async (token: string) => {
    const url = `${window.location.origin}/c/${token}`
    try { await navigator.clipboard.writeText(url); setCopied(token); setTimeout(() => setCopied(null), 1500) } catch { /* noop */ }
  }

  const setResponsable = async (id: string, email: string) => {
    try {
      const updated = await patchCompromiso(id, { responsable_email: email })
      setItems(prev => (prev ?? []).map(c => (c.id === id ? updated : c)))
    } catch { /* noop */ }
  }

  if (items === null) return <p className="text-sm text-gray-400">Cargando compromisos…</p>
  if (items.length === 0) return <p className="text-sm text-gray-400">Aún no hay compromisos. Cierra decisiones en la Minuta para generarlos.</p>

  return (
    <div className="space-y-3">
      {items.map(c => {
        const n = NUDGE[c.nudge] ?? NUDGE.al_dia
        return (
          <div key={c.id} className="rounded-2xl border border-gray-100 bg-white p-4">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <h4 className="text-sm font-medium text-black">{c.descripcion}</h4>
              <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${n.cls}`}>{n.label}</span>
            </div>
            {c.fecha_compromiso && <p className="text-xs text-gray-400 mt-1">Vence: {c.fecha_compromiso}</p>}
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              <input
                type="email"
                defaultValue={c.responsable_email ?? ""}
                placeholder="email del responsable"
                onBlur={e => { if (e.target.value !== (c.responsable_email ?? "")) setResponsable(c.id, e.target.value) }}
                className="border border-gray-200 rounded-lg px-2 py-1 text-xs flex-1 min-w-[160px]"
              />
              <button type="button" onClick={() => copyLink(c.token)}
                className="text-xs font-medium text-[var(--gob-navy)] hover:underline">
                {copied === c.token ? "¡Copiado!" : "Copiar link"}
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
