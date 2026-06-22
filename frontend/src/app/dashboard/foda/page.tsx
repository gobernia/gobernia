"use client"

import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import { Loader2, TrendingUp, Compass, AlertTriangle, ShieldAlert } from "lucide-react"
import { Foda, FodaOut, getFoda } from "@/lib/foda"

type Quad = { key: keyof Foda; label: string; icon: typeof TrendingUp; accent: string; chip: string }
const QUADS: Quad[] = [
  { key: "fortalezas", label: "Fortalezas", icon: TrendingUp, accent: "border-t-green-500", chip: "text-green-700 bg-green-50" },
  { key: "oportunidades", label: "Oportunidades", icon: Compass, accent: "border-t-[var(--gob-navy)]", chip: "text-[var(--gob-navy)] bg-blue-50" },
  { key: "debilidades", label: "Debilidades", icon: AlertTriangle, accent: "border-t-amber-500", chip: "text-amber-700 bg-amber-50" },
  { key: "amenazas", label: "Amenazas", icon: ShieldAlert, accent: "border-t-red-500", chip: "text-red-700 bg-red-50" },
]

export default function FodaPage() {
  const [data, setData] = useState<FodaOut | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const d = await getFoda()
        if (!alive) return
        setData(d)
        if (d.status === "generating") timer.current = setTimeout(tick, 4000)
      } catch { /* reintenta al recargar */ }
    }
    tick()
    return () => { alive = false; if (timer.current) clearTimeout(timer.current) }
  }, [])

  const f = data?.foda

  return (
    <div className="min-h-dvh bg-white text-black">
      <main className="max-w-5xl mx-auto px-[var(--px-fluid)] py-12 space-y-10">
        <div>
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Análisis estratégico</p>
          <h1 className="text-3xl font-bold tracking-tight">Matriz FODA</h1>
        </div>

        {(!data || data.status === "generating") && (
          <div className="border border-gray-100 rounded-2xl p-16 flex flex-col items-center justify-center gap-3 text-center">
            <Loader2 className="h-6 w-6 animate-spin text-gray-300" />
            <p className="text-sm text-gray-500">Todd está cruzando tu información interna y externa para armar la matriz…</p>
          </div>
        )}

        {data?.status === "failed" && (
          <div className="border border-gray-100 rounded-2xl p-12 text-center text-sm text-gray-500">
            No se pudo generar la matriz. Vuelve a confirmar tus metas para reintentar.
          </div>
        )}

        {data?.status === "active" && f && (
          <>
            {f.sintesis && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                className="bg-[var(--gob-navy)] text-[var(--gob-bone)] rounded-2xl p-6">
                <p className="text-[10px] font-medium tracking-widest uppercase opacity-70 mb-1.5">Síntesis</p>
                <p className="text-sm leading-relaxed">{f.sintesis}</p>
              </motion.div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              {QUADS.map((q, i) => {
                const Icon = q.icon
                const items = (f[q.key] as string[]) || []
                return (
                  <motion.section key={q.key}
                    initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 + i * 0.06 }}
                    className={`border border-gray-100 border-t-4 ${q.accent} rounded-2xl p-5`}>
                    <div className="flex items-center gap-2 mb-3">
                      <span className={`h-7 w-7 rounded-lg flex items-center justify-center ${q.chip}`}>
                        <Icon className="h-4 w-4" />
                      </span>
                      <h2 className="text-sm font-bold tracking-wide uppercase">{q.label}</h2>
                    </div>
                    {items.length > 0 ? (
                      <ul className="space-y-2">
                        {items.map((t, j) => (
                          <li key={j} className="text-sm text-gray-700 leading-snug flex gap-2">
                            <span className="text-gray-300">•</span><span>{t}</span>
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-xs text-gray-300 italic">Sin elementos.</p>}
                  </motion.section>
                )
              })}
            </div>

            {(f.metas_priorizadas?.length ?? 0) > 0 && (
              <section className="space-y-3 pt-2">
                <h2 className="text-xl font-bold tracking-tight">Tus prioridades</h2>
                <ol className="space-y-2">
                  {f.metas_priorizadas.map((m, i) => (
                    <li key={i} className="flex items-center gap-3 border border-gray-100 rounded-xl px-4 py-2.5">
                      <span className="w-6 h-6 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                      <span className="text-sm">{m}</span>
                    </li>
                  ))}
                </ol>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  )
}
