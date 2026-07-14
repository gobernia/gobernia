"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Loader2, TrendingUp, Compass, AlertTriangle, ShieldAlert, ArrowRight, Download } from "lucide-react"
import { PageShell, PageHeader, Prose } from "@/components/ui/PageShell"
import { Foda, FodaOut, getFoda, downloadFodaPdf } from "@/lib/foda"
import { generateAnnualPlan } from "@/lib/annualPlan"

/**
 * La matriz se lee como matriz: columnas = origen (interno / externo),
 * filas = signo (a favor / en contra). El orden de QUADS ES el orden de las celdas.
 *   Fortalezas   | Oportunidades
 *   Debilidades  | Amenazas
 * `cell` lleva los bordes de la celda como clases literales (Tailwind v4 no
 * detecta clases construidas al vuelo).
 */
type Quad = {
  key: keyof Foda; label: string; signo: string; icon: typeof TrendingUp
  bar: string; chip: string; cell: string
}
const QUADS: Quad[] = [
  {
    key: "fortalezas", label: "Fortalezas", signo: "A favor", icon: TrendingUp,
    bar: "bg-green-500", chip: "text-green-700 bg-green-50",
    cell: "border-b border-gray-100 lg:border-r",
  },
  {
    key: "oportunidades", label: "Oportunidades", signo: "A favor", icon: Compass,
    bar: "bg-[var(--gob-navy)]", chip: "text-[var(--gob-navy)] bg-blue-50",
    cell: "border-b border-gray-100",
  },
  {
    key: "debilidades", label: "Debilidades", signo: "En contra", icon: AlertTriangle,
    bar: "bg-amber-500", chip: "text-amber-700 bg-amber-50",
    cell: "border-b border-gray-100 lg:border-r lg:border-b-0",
  },
  {
    key: "amenazas", label: "Amenazas", signo: "En contra", icon: ShieldAlert,
    bar: "bg-red-500", chip: "text-red-700 bg-red-50",
    cell: "",
  },
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
      <PageHeader
        eyebrow="Análisis estratégico"
        title="Matriz FODA"
        actions={isActive ? (
          <>
            <button onClick={onDownload} disabled={downloading}
              className="inline-flex items-center gap-2 border border-gray-200 text-sm font-medium text-gray-700 px-3.5 py-2.5 rounded-xl hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              PDF
            </button>
            <button onClick={generarPlan} disabled={generando}
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-4 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              {generando ? <><Loader2 className="h-4 w-4 animate-spin" /> Generando…</> : <>
                <span className="hidden sm:inline">Generar mi plan a 3 años</span>
                <span className="sm:hidden">Generar plan</span>
                <ArrowRight className="h-4 w-4" />
              </>}
            </button>
          </>
        ) : undefined}
      />

      <main>
        <PageShell className="py-10 space-y-8">

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
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
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
            <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_340px] xl:items-start">

              {/* La matriz: protagonista de la pantalla */}
              <section className="min-w-0 space-y-3">
                {/* Ejes: origen del factor */}
                <div className="hidden lg:grid grid-cols-2">
                  <p className="pl-7 text-[10px] font-medium uppercase tracking-[0.18em] text-[var(--gob-stone)]">Origen interno</p>
                  <p className="pl-7 text-[10px] font-medium uppercase tracking-[0.18em] text-[var(--gob-stone)]">Origen externo</p>
                </div>

                <div className="grid rounded-2xl border border-gray-200 overflow-hidden lg:grid-cols-2">
                  {QUADS.map((q, i) => {
                    const Icon = q.icon
                    const items = (f[q.key] as string[]) || []
                    return (
                      <motion.div key={q.key}
                        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.05 + i * 0.06 }}
                        className={`p-6 lg:p-7 lg:min-h-[300px] ${q.cell}`}>
                        <div className="flex items-center gap-2.5 mb-4">
                          <span className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${q.chip}`}>
                            <Icon className="h-4 w-4" />
                          </span>
                          <div className="min-w-0">
                            <h2 className="text-base font-bold tracking-tight text-black">{q.label}</h2>
                            <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-gray-400">{q.signo}</p>
                          </div>
                        </div>
                        <div className={`h-1 w-12 rounded-full mb-4 ${q.bar}`} />
                        {items.length > 0 ? (
                          <ul className="space-y-2.5">
                            {items.map((t, j) => (
                              <li key={j} className="text-sm text-gray-700 leading-snug flex gap-2.5">
                                <span className="text-gray-300 shrink-0">•</span><span>{t}</span>
                              </li>
                            ))}
                          </ul>
                        ) : <p className="text-xs text-gray-300 italic">Sin elementos.</p>}
                      </motion.div>
                    )
                  })}
                </div>
              </section>

              {/* Rail: la síntesis ejecutiva y el paso siguiente */}
              <aside className="space-y-4 xl:sticky xl:top-24">
                {f.sintesis && (
                  <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                    className="bg-[var(--gob-navy)] text-[var(--gob-bone)] rounded-2xl p-6">
                    <p className="text-[10px] font-medium tracking-[0.18em] uppercase opacity-70 mb-2">Síntesis</p>
                    <Prose>
                      <p className="text-sm leading-relaxed">{f.sintesis}</p>
                    </Prose>
                  </motion.div>
                )}

                <div className="rounded-2xl border border-gray-100 p-5 space-y-3">
                  <p className="text-sm text-gray-500 leading-relaxed">
                    Con la matriz lista, tu consejo puede convertirla en un plan de trabajo a tres años.
                  </p>
                  <button onClick={generarPlan} disabled={generando}
                    className="w-full inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
                    {generando ? <><Loader2 className="h-4 w-4 animate-spin" /> Generando tu plan…</> : <>Generar mi plan a 3 años <ArrowRight className="h-4 w-4" /></>}
                  </button>
                  {genErr && <p className="text-xs text-red-500">{genErr}</p>}
                </div>
              </aside>
            </div>
          )}
        </PageShell>
      </main>
    </div>
  )
}
