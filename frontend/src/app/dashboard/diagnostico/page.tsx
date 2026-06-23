"use client"

import { useState, useEffect, useCallback, useRef, type ReactNode } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import {
  Loader2, Sparkles, AlertCircle, Download, FileSearch, ChevronDown, ArrowRight,
  TrendingUp, TrendingDown, Minus, Link2,
} from "lucide-react"
import {
  getDiagnostico, getDiagnosticoStatus, generateDiagnostico, downloadDiagnosticoPdf,
  type Diagnostico, type Hallazgo,
} from "@/lib/diagnostico"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

type View = "loading" | "none" | "generating" | "failed" | "active" | "error"

// --- Acordeón reutilizable -------------------------------------------------
function Accordion({ title, defaultOpen = false, highlight = false, badge, children }: {
  title: string; defaultOpen?: boolean; highlight?: boolean; badge?: ReactNode; children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className={`rounded-2xl border transition-colors ${
      open ? "border-gray-200" : "border-gray-100 hover:border-gray-200"
    } ${highlight ? "border-l-2 border-l-[var(--gob-navy)]" : ""}`}>
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left">
        <span className="flex items-center gap-2.5 min-w-0">
          <h2 className="text-base font-bold text-black tracking-tight truncate">{title}</h2>
          {badge}
        </span>
        <ChevronDown className={`h-4 w-4 text-gray-400 shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25, ease: EASE }}
            className="overflow-hidden">
            <div className="px-5 pb-5 pt-0">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// --- Clasificación visual de hallazgos -------------------------------------
const TIPO_META: Record<string, { Icon: typeof TrendingUp; color: string; bg: string; border: string; label: string }> = {
  fortaleza: { Icon: TrendingUp, color: "text-green-600", bg: "bg-green-50", border: "border-l-green-500", label: "Fortaleza" },
  debilidad: { Icon: TrendingDown, color: "text-red-500", bg: "bg-red-50", border: "border-l-red-500", label: "Debilidad" },
  parcial: { Icon: Minus, color: "text-amber-500", bg: "bg-amber-50", border: "border-l-amber-500", label: "A mejorar" },
}
const tipoMeta = (t: string) =>
  TIPO_META[t] ?? { Icon: Minus, color: "text-gray-400", bg: "bg-gray-50", border: "border-l-gray-300", label: "Nota" }
// Orden para mostrar: fortalezas, luego a-mejorar, luego debilidades
const TIPO_ORDER: Record<string, number> = { fortaleza: 0, parcial: 1, debilidad: 2 }
const sortHallazgos = (items: Hallazgo[]) =>
  [...items].sort((a, b) => (TIPO_ORDER[a.tipo] ?? 3) - (TIPO_ORDER[b.tipo] ?? 3))

export default function DiagnosticoPage() {
  const [view, setView] = useState<View>("loading")
  const [diag, setDiag] = useState<Diagnostico | null>(null)
  const [failReason, setFailReason] = useState<"datos" | "general" | null>(null)
  const [failDetail, setFailDetail] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }, [])

  const loadDiag = useCallback(async () => {
    const d = await getDiagnostico()
    setDiag(d)
    setView("active")
  }, [])

  const startPolling = useCallback(() => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const s = await getDiagnosticoStatus()
        if (s.status === "active") { stopPolling(); await loadDiag() }
        else if (s.status === "failed") { stopPolling(); setFailReason("general"); setView("failed") }
      } catch { /* reintenta en el próximo tick */ }
    }, 2500)
  }, [stopPolling, loadDiag])

  const init = useCallback(async () => {
    try {
      const s = await getDiagnosticoStatus()
      if (s.status === "generating") { setView("generating"); startPolling() }
      else if (s.status === "failed") { setView("failed") }
      else await loadDiag()
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) setView("none")
      else setView("error")
    }
  }, [startPolling, loadDiag])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { init(); return () => stopPolling() }, [init, stopPolling])

  const onGenerate = async () => {
    setView("generating")
    setFailReason(null); setFailDetail(null)
    try {
      await generateDiagnostico()
      startPolling()
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (status === 400) { setFailReason("datos"); setFailDetail(detail ?? null) }
      else setFailReason("general")
      setView("failed")
    }
  }

  const onDownload = async () => {
    setDownloading(true)
    try { await downloadDiagnosticoPdf() } catch { /* noop */ } finally { setDownloading(false) }
  }

  if (view === "loading") {
    return <div className="min-h-dvh bg-white flex items-center justify-center">
      <Loader2 className="h-5 w-5 animate-spin text-gray-300" />
    </div>
  }

  if (view === "generating") {
    return (
      <div className="min-h-dvh bg-white flex flex-col items-center justify-center gap-6 px-6 text-center">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--gob-navy)]" />
        <div className="space-y-1">
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Investigando</p>
          <h1 className="text-2xl font-bold text-black">Tu consejo está investigando tu empresa en la web</h1>
          <p className="text-sm text-gray-500 max-w-md">
            Analiza tu presencia digital, competidores reales, tendencias de mercado y contexto de tu región.
            Esto puede tardar unos minutos.
          </p>
        </div>
      </div>
    )
  }

  if (view === "none" || view === "failed" || view === "error") {
    const isFail = view === "failed" || view === "error"
    const isDatos = isFail && failReason === "datos"
    return (
      <div className="min-h-dvh bg-white flex flex-col items-center justify-center gap-6 px-6 text-center">
        <div className="w-14 h-14 rounded-2xl border-2 border-gray-100 flex items-center justify-center">
          {isFail ? <AlertCircle className="h-5 w-5 text-red-400" /> : <FileSearch className="h-5 w-5 text-gray-300" />}
        </div>
        <div className="space-y-2 max-w-md">
          <p className="text-base font-medium text-black">
            {isDatos ? "Completa los datos de tu empresa"
              : isFail ? "No se pudo generar el diagnóstico"
              : "Genera tu diagnóstico estratégico"}
          </p>
          <p className="text-sm text-gray-500 leading-relaxed">
            {isDatos ? (failDetail ?? "Para investigar tu empresa necesito tu página web y tus competidores. Complétalos en tu onboarding.")
              : isFail ? "Algo falló al investigar. Puedes reintentarlo."
              : "Investigaré tu empresa en la web —presencia digital, competidores reales, mercado y contexto— y armaré un diagnóstico con fuentes. Tarda unos minutos."}
          </p>
        </div>
        {isDatos ? (
          <Link href="/dashboard/datos"
            className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
            Completar mis datos
          </Link>
        ) : (
          <button onClick={onGenerate}
            className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
            <Sparkles className="h-4 w-4" /> {isFail ? "Reintentar" : "Generar diagnóstico"}
          </button>
        )}
      </div>
    )
  }

  const fd = Object.entries(diag?.fortalezas_debilidades ?? {})
  const sources = diag?.sources ?? []

  return (
    <div className="min-h-dvh bg-white text-black antialiased">
      {/* Barra superior sticky con acciones */}
      <div className="sticky top-0 z-20 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="w-full max-w-3xl mx-auto px-[var(--px-fluid)] py-3.5 flex items-center justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Diagnóstico estratégico</p>
            <h1 className="text-lg sm:text-xl font-bold text-black tracking-tight truncate">La realidad de tu empresa</h1>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={onDownload} disabled={downloading}
              className="inline-flex items-center gap-2 border border-gray-200 text-sm font-medium text-gray-700 px-3.5 py-2.5 rounded-xl hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors disabled:opacity-50">
              {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              PDF
            </button>
            <a href="/onboarding/todd/externo"
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-4 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
              <span className="hidden sm:inline">Continuar al análisis del entorno</span>
              <span className="sm:hidden">Continuar</span>
              <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </div>
      </div>

      <main>
        <div className="w-full max-w-3xl mx-auto px-[var(--px-fluid)] py-8 space-y-8">

          {/* Secciones en acordeones */}
          <div className="space-y-3">
            {(diag?.sections ?? []).map((s, i) => (
              <motion.div key={s.key} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, ease: EASE, delay: i * 0.04 }}>
                <Accordion title={s.title} defaultOpen={i === 0} highlight={s.key === "competencia"}>
                  <div className="space-y-3">
                    {(s.body || "").split("\n").filter(p => p.trim()).map((p, j) => (
                      <p key={j} className="text-[15px] text-gray-700 leading-relaxed">{p.trim()}</p>
                    ))}
                    {!s.body && <p className="text-sm text-gray-300 italic">Sin contenido.</p>}
                  </div>
                </Accordion>
              </motion.div>
            ))}
          </div>

          {/* Fortalezas y debilidades — tarjetas ordenadas por área */}
          {fd.length > 0 && (
            <section className="space-y-4 pt-2">
              <div className="flex items-center justify-between gap-4 flex-wrap">
                <h2 className="text-xl font-bold text-black tracking-tight">Fortalezas y debilidades</h2>
                <div className="flex items-center gap-3 text-[11px] text-gray-400">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> Fortaleza</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> A mejorar</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Debilidad</span>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {fd.map(([area, items]) => {
                  const ordered = sortHallazgos(items)
                  const accent = tipoMeta(ordered[0]?.tipo ?? "").border
                  return (
                    <div key={area} className={`rounded-2xl border border-gray-100 border-l-4 ${accent} p-4 space-y-2.5`}>
                      <p className="text-xs font-semibold tracking-wide text-gray-500 uppercase">{area}</p>
                      <ul className="space-y-2">
                        {ordered.map((h, j) => {
                          const m = tipoMeta(h.tipo)
                          return (
                            <li key={j} className="flex items-start gap-2.5 text-sm">
                              <span className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${m.bg}`}>
                                <m.Icon className={`h-3 w-3 ${m.color}`} />
                              </span>
                              <span className="text-gray-700 leading-snug">{h.texto}</span>
                            </li>
                          )
                        })}
                      </ul>
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          {/* Fuentes — colapsable */}
          {sources.length > 0 && (
            <Accordion title="Fuentes" badge={
              <span className="text-xs font-medium text-gray-400 bg-gray-50 rounded-full px-2 py-0.5">{sources.length}</span>
            }>
              <ul className="space-y-1.5">
                {sources.map((src, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-gray-500">
                    <Link2 className="h-3.5 w-3.5 text-gray-300 mt-0.5 shrink-0" />
                    <a href={src.url} target="_blank" rel="noopener noreferrer"
                      className="hover:text-[var(--gob-navy)] underline decoration-gray-200">
                      {src.title}
                    </a>
                  </li>
                ))}
              </ul>
            </Accordion>
          )}

          {/* Pie: regenerar + continuar */}
          <div className="pt-2 flex items-center justify-between gap-4 border-t border-gray-100 mt-2">
            <button onClick={onGenerate}
              className="text-xs font-medium text-gray-400 hover:text-[var(--gob-navy)] transition-colors pt-4">
              Regenerar diagnóstico
            </button>
            <a href="/onboarding/todd/externo"
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors mt-4">
              Continuar al análisis del entorno <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </div>
      </main>
    </div>
  )
}
