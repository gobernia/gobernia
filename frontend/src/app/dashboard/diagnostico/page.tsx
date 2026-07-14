"use client"

import { useState, useEffect, useCallback, useRef, type ReactNode } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import {
  Loader2, Sparkles, AlertCircle, Download, FileSearch, ChevronDown, ArrowRight,
  TrendingUp, TrendingDown, Minus, Link2, ShieldAlert, Globe,
} from "lucide-react"
import { PageShell, PageHeader, Prose } from "@/components/ui/PageShell"
import {
  getDiagnostico, getDiagnosticoStatus, generateDiagnostico, downloadDiagnosticoPdf,
  type Diagnostico,
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
        className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
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

// Severidad de riesgos → color coding
const SEV_META: Record<string, { chip: string; dot: string; label: string }> = {
  alta: { chip: "text-red-700 bg-red-50", dot: "bg-red-500", label: "Alta" },
  media: { chip: "text-amber-700 bg-amber-50", dot: "bg-amber-500", label: "Media" },
  baja: { chip: "text-gray-600 bg-gray-100", dot: "bg-gray-400", label: "Baja" },
}
const sevMeta = (s: string) => SEV_META[s] ?? SEV_META.media
const SEV_ORDER: Record<string, number> = { alta: 0, media: 1, baja: 2 }

// Cifra de cabecera: lo que el diagnóstico encontró, de un vistazo.
function Stat({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className="rounded-2xl border border-gray-100 px-5 py-4">
      <p className={`text-2xl font-bold tracking-tight ${accent}`}>{value}</p>
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-gray-400 mt-0.5">{label}</p>
    </div>
  )
}

// Bloque interno reutilizable (Fortalezas / Debilidades): tarjeta con acento superior + lista.
type Cubi = { area: string; tipo: string; texto: string }
function InternalBlock({ title, Icon, iconColor, accent, items }: {
  title: string; Icon: typeof TrendingUp; iconColor: string; accent: string; items: Cubi[]
}) {
  if (items.length === 0) return null
  return (
    <section className={`rounded-2xl border border-gray-100 border-t-4 ${accent} p-5 space-y-3`}>
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 ${iconColor}`} />
        <h2 className="text-base font-bold text-black tracking-tight">{title}</h2>
        <span className="text-xs font-medium text-gray-400 bg-gray-50 rounded-full px-2 py-0.5">{items.length}</span>
      </div>
      <ul className="space-y-2.5">
        {items.map((h, i) => {
          const m = tipoMeta(h.tipo)
          return (
            <li key={i} className="flex items-start gap-2.5 text-sm">
              <span className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${m.bg}`}>
                <m.Icon className={`h-3 w-3 ${m.color}`} />
              </span>
              <span className="text-gray-700 leading-snug">
                {h.texto}
                {h.area && <span className="ml-1.5 text-[11px] text-gray-400 uppercase tracking-wide">· {h.area}</span>}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

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
            className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
            Completar mis datos
          </Link>
        ) : (
          <button onClick={onGenerate}
            className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
            <Sparkles className="h-4 w-4" /> {isFail ? "Reintentar" : "Generar diagnóstico"}
          </button>
        )}
      </div>
    )
  }

  const flat: Cubi[] = Object.entries(diag?.fortalezas_debilidades ?? {})
    .flatMap(([area, items]) => items.map(h => ({ area, tipo: h.tipo, texto: h.texto })))
  const fortalezas = flat.filter(h => h.tipo === "fortaleza")
  const debilidades = flat.filter(h => h.tipo === "debilidad" || h.tipo === "parcial")
  const riesgos = [...(diag?.riesgos ?? [])].sort(
    (a, b) => (SEV_ORDER[a.severidad] ?? 1) - (SEV_ORDER[b.severidad] ?? 1))
  const sources = diag?.sources ?? []
  const sections = (diag?.sections ?? []).filter(s => s.body)
  const sinInterno = fortalezas.length === 0 && debilidades.length === 0 && riesgos.length === 0
  const hayCifras = fortalezas.length > 0 || debilidades.length > 0 || riesgos.length > 0

  return (
    <div className="min-h-dvh bg-white text-black antialiased">
      <PageHeader
        eyebrow="Diagnóstico estratégico"
        title="La realidad de tu empresa"
        actions={
          <>
            <button onClick={onDownload} disabled={downloading}
              className="inline-flex items-center gap-2 border border-gray-200 text-sm font-medium text-gray-700 px-3.5 py-2.5 rounded-xl hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              PDF
            </button>
            <a href="/onboarding/todd/externo"
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-4 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              <span className="hidden sm:inline">Continuar al análisis del entorno</span>
              <span className="sm:hidden">Continuar</span>
              <ArrowRight className="h-4 w-4" />
            </a>
          </>
        }
      />

      <main>
        <PageShell className="py-8 space-y-6">

          {/* Resumen: qué encontró el diagnóstico, de un vistazo */}
          {hayCifras && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Fortalezas" value={fortalezas.length} accent="text-green-600" />
              <Stat label="Debilidades" value={debilidades.length} accent="text-red-500" />
              <Stat label="Riesgos" value={riesgos.length} accent="text-amber-500" />
              <Stat label="Fuentes consultadas" value={sources.length} accent="text-[var(--gob-navy)]" />
            </div>
          )}

          {/* Lienzo ancho: la lectura a la izquierda, lo accionable a la derecha */}
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-8 lg:items-start">

            {/* Columna de lectura ------------------------------------------------ */}
            <div className="min-w-0 space-y-4">
              {/* Hallazgos internos: dos columnas en pantallas grandes */}
              <div className="grid gap-4 xl:grid-cols-2 xl:items-start">
                <InternalBlock title="Fortalezas internas" Icon={TrendingUp} iconColor="text-green-600"
                  accent="border-t-green-500" items={fortalezas} />
                <InternalBlock title="Debilidades internas" Icon={TrendingDown} iconColor="text-red-500"
                  accent="border-t-red-500" items={debilidades} />
              </div>

              {sinInterno && (
                <p className="text-sm text-gray-400 py-2">
                  Aún no hay hallazgos internos. Complétalos platicando con Todd — aquí tienes el contexto de mercado.
                </p>
              )}

              {/* Contexto de mercado (investigación web) — acordeón */}
              {sections.length > 0 && (
                <Accordion title="Contexto de mercado" defaultOpen={sinInterno} badge={
                  <span className="inline-flex items-center gap-1 text-[11px] text-gray-400">
                    <Globe className="h-3 w-3" /> investigación web
                  </span>
                }>
                  <div className="space-y-6">
                    {sections.map(s => (
                      <div key={s.key} className="space-y-1.5">
                        <h3 className="text-sm font-bold text-black">{s.title}</h3>
                        <Prose className="space-y-2">
                          {s.body.split("\n").filter(p => p.trim()).map((p, j) => (
                            <p key={j} className="text-[14px] text-gray-600 leading-relaxed">{p.trim()}</p>
                          ))}
                        </Prose>
                      </div>
                    ))}
                  </div>
                </Accordion>
              )}
            </div>

            {/* Columna de apoyo: lo accionable primero ---------------------------- */}
            <aside className="space-y-4 lg:sticky lg:top-24">
              {riesgos.length > 0 && (
                <section className="rounded-2xl border border-gray-100 border-t-4 border-t-amber-500 p-5 space-y-3">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-amber-500" />
                    <h2 className="text-base font-bold text-black tracking-tight">Riesgos</h2>
                    <span className="text-xs font-medium text-gray-400 bg-gray-50 rounded-full px-2 py-0.5">{riesgos.length}</span>
                  </div>
                  <ul className="space-y-3">
                    {riesgos.map((r, i) => {
                      const m = sevMeta(r.severidad)
                      return (
                        <li key={i} className="space-y-1.5">
                          <span className={`inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full ${m.chip}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${m.dot}`} /> {m.label}
                          </span>
                          <p className="text-sm text-gray-700 leading-snug">{r.riesgo}</p>
                        </li>
                      )
                    })}
                  </ul>
                </section>
              )}

              {sources.length > 0 && (
                <Accordion title="Fuentes" badge={
                  <span className="text-xs font-medium text-gray-400 bg-gray-50 rounded-full px-2 py-0.5">{sources.length}</span>
                }>
                  <ul className="space-y-1.5">
                    {sources.map((src, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-gray-500">
                        <Link2 className="h-3.5 w-3.5 text-gray-300 mt-0.5 shrink-0" />
                        <a href={src.url} target="_blank" rel="noopener noreferrer"
                          className="hover:text-[var(--gob-navy)] underline decoration-gray-200 break-words focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
                          {src.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </Accordion>
              )}
            </aside>
          </div>

          {/* Pie: regenerar + continuar */}
          <div className="pt-4 flex items-center justify-between gap-4 flex-wrap border-t border-gray-100">
            <button onClick={onGenerate}
              className="text-xs font-medium text-gray-400 hover:text-[var(--gob-navy)] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)] rounded">
              Regenerar diagnóstico
            </button>
            <a href="/onboarding/todd/externo"
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              Continuar al análisis del entorno <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </PageShell>
      </main>
    </div>
  )
}
