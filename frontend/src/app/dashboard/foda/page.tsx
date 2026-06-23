"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Loader2, TrendingUp, Compass, AlertTriangle, ShieldAlert, ArrowRight, Download } from "lucide-react"
import { Foda, FodaOut, getFoda, downloadFodaPdf } from "@/lib/foda"
import { generateAnnualPlan } from "@/lib/annualPlan"

type Quad = { key: keyof Foda; label: string; icon: typeof TrendingUp; accent: string; chip: string }
const QUADS: Quad[] = [
  { key: "fortalezas", label: "Fortalezas", icon: TrendingUp, accent: "border-t-green-500", chip: "text-green-700 bg-green-50" },
  { key: "oportunidades", label: "Oportunidades", icon: Compass, accent: "border-t-[var(--gob-navy)]", chip: "text-[var(--gob-navy)] bg-blue-50" },
  { key: "debilidades", label: "Debilidades", icon: AlertTriangle, accent: "border-t-amber-500", chip: "text-amber-700 bg-amber-50" },
  { key: "amenazas", label: "Amenazas", icon: ShieldAlert, accent: "border-t-red-500", chip: "text-red-700 bg-red-50" },
]

export default function FodaPage() {
  const router = useRouter()
  const [data, setData] = useState<FodaOut | null>(null)
  const [generando, setGenerando] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [genErr, setGenErr] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const generarPlan = async () => {
    setGenerando(true); setGenErr(null)
    try { await generateAnnualPlan(3); router.push("/dashboard/plan") }
    catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setGenErr(detail ?? "No se pudo iniciar la generación del plan. Intenta de nuevo.")
      setGenerando(false)
    }
  }

  const onDownload = async () => {
    setDownloading(true)
    try { await downloadFodaPdf() } catch { /* noop */ } finally { setDownloading(false) }
  }

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

  const isActive = data?.status === "active" && !!f

  return (
    <div className="min-h-dvh bg-white text-black">
      {/* Header sticky con acciones (cuando la matriz está lista) */}
      <div className="sticky top-0 z-20 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-[var(--px-fluid)] py-3.5 flex items-center justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Análisis estratégico</p>
            <h1 className="text-lg sm:text-xl font-bold tracking-tight truncate">Matriz FODA</h1>
          </div>
          {isActive && (
            <div className="flex items-center gap-2 shrink-0">
              <button onClick={onDownload} disabled={downloading}
                className="inline-flex items-center gap-2 border border-gray-200 text-sm font-medium text-gray-700 px-3.5 py-2.5 rounded-xl hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors disabled:opacity-50">
                {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                PDF
              </button>
              <button onClick={generarPlan} disabled={generando}
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-4 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50">
                {generando ? <><Loader2 className="h-4 w-4 animate-spin" /> Generando…</> : <>
                  <span className="hidden sm:inline">Generar mi plan a 3 años</span>
                  <span className="sm:hidden">Generar plan</span>
                  <ArrowRight className="h-4 w-4" />
                </>}
              </button>
            </div>
          )}
        </div>
      </div>

      <main className="max-w-5xl mx-auto px-[var(--px-fluid)] py-10 space-y-10">

        {!data && (
          <div className="border border-gray-100 rounded-2xl p-16 flex items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-gray-300" />
          </div>
        )}

        {data?.status === "none" && (
          <div className="border border-gray-100 rounded-2xl p-12 sm:p-16 flex flex-col items-center justify-center text-center gap-4">
            <div className="w-14 h-14 rounded-2xl border-2 border-gray-100 flex items-center justify-center">
              <Compass className="h-5 w-5 text-gray-300" />
            </div>
            <div className="space-y-2 max-w-md">
              <p className="text-base font-medium text-black">Aún no has construido tu matriz FODA</p>
              <p className="text-sm text-gray-500 leading-relaxed">
                La matriz FODA se arma cruzando tu diagnóstico con el <strong>análisis del entorno</strong> y
                la priorización de tus metas. Continúa con el análisis para construirla.
              </p>
            </div>
            <a href="/onboarding/todd/externo"
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
              Continuar al análisis del entorno <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        )}

        {data?.status === "generating" && (
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

            <div className="pt-2 space-y-2">
              <button onClick={generarPlan} disabled={generando}
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50">
                {generando ? <><Loader2 className="h-4 w-4 animate-spin" /> Generando tu plan…</> : "Generar mi plan a 3 años →"}
              </button>
              {genErr && <p className="text-xs text-red-500 max-w-md">{genErr}</p>}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
