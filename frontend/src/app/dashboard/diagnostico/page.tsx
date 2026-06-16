"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Loader2, Sparkles, AlertCircle, Download, FileSearch } from "lucide-react"
import {
  getDiagnostico, getDiagnosticoStatus, generateDiagnostico, downloadDiagnosticoPdf,
  type Diagnostico,
} from "@/lib/diagnostico"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

type View = "loading" | "none" | "generating" | "failed" | "active" | "error"

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
          <Link href="/onboarding/etapa-1"
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

  return (
    <div className="min-h-dvh bg-white text-black antialiased">
      <main>
        <div className="w-full max-w-3xl mx-auto px-[var(--px-fluid)] py-12 space-y-8">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE }} className="flex items-start justify-between gap-4 flex-wrap">
            <div className="space-y-1">
              <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Diagnóstico estratégico</p>
              <h1 className="text-3xl font-bold text-black tracking-tight">La realidad de tu empresa</h1>
            </div>
            <button onClick={onDownload} disabled={downloading}
              className="inline-flex items-center gap-2 border border-gray-200 text-sm font-medium text-gray-700 px-4 py-2.5 rounded-xl hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors disabled:opacity-50">
              {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              PDF
            </button>
          </motion.div>

          {(diag?.sections ?? []).map((s, i) => {
            const highlight = s.key === "competencia"
            return (
              <motion.section key={s.key} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: EASE, delay: 0.05 + i * 0.05 }}
                className={`space-y-3 ${highlight ? "border-l-2 border-[var(--gob-navy)] pl-5" : ""}`}>
                <h2 className="text-xl font-bold text-black tracking-tight">{s.title}</h2>
                <div className="space-y-3">
                  {(s.body || "").split("\n").filter(p => p.trim()).map((p, j) => (
                    <p key={j} className="text-[15px] text-gray-700 leading-relaxed">{p.trim()}</p>
                  ))}
                  {!s.body && <p className="text-sm text-gray-300 italic">Sin contenido.</p>}
                </div>
              </motion.section>
            )
          })}

          {(diag?.sources ?? []).length > 0 && (
            <section className="space-y-2 pt-4 border-t border-gray-100">
              <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Fuentes</p>
              <ul className="space-y-1">
                {diag!.sources.map((src, i) => (
                  <li key={i} className="text-xs text-gray-500">
                    <a href={src.url} target="_blank" rel="noopener noreferrer"
                      className="hover:text-[var(--gob-navy)] underline decoration-gray-200">
                      {src.title}
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <div className="pt-4">
            <button onClick={onGenerate}
              className="text-xs font-medium text-gray-400 hover:text-[var(--gob-navy)] transition-colors">
              Regenerar diagnóstico
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
