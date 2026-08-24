"use client"

import { useState, useEffect, useCallback, useRef, type ReactNode, type CSSProperties } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import {
  Loader2, Sparkles, AlertCircle, Download, FileSearch, ChevronDown, ArrowRight,
  TrendingUp, TrendingDown, Link2, ShieldAlert, Globe, Compass, AlertTriangle, LayoutGrid,
} from "lucide-react"
import { PageShell } from "@/components/ui/PageShell"
import {
  getDiagnostico, getDiagnosticoStatus, generateDiagnostico, downloadDiagnosticoPdf,
  type Diagnostico,
} from "@/lib/diagnostico"
import { getFoda, type Foda, type FodaOut } from "@/lib/foda"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

type View = "loading" | "none" | "generating" | "failed" | "active" | "error"

// Paleta por hex — Tailwind v4 no detecta clases dinámicas, así que los colores
// de acento se aplican con `style`. Mismos tokens del bento del Inicio.
const PAPER = "#F2F2F0"
const INK   = "#0E1626"
const INK2  = "#39435A"
const MUTED = "#6E7686"
const CARD  = "#FFFFFF"
const SAND  = "#E8E3D8"
const BNAVY = "#152742"
const ACCENT = "#FF5C1A"
const LINE  = "#E2E2DC"
// Colores semánticos del FODA (se mantienen).
const GREEN = "#0f766e"
const AMBER = "#b45309"
const RED = "#b91c1c"
const RESUMEN_KEY = "resumen_ejecutivo"
// El CSS global pone h1/h2/h3 en serif (Newsreader). En el bento NO queremos
// serif: forzamos sans (Inter) en cada título, igual que el Inicio.
const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }

// --- Acordeón reutilizable -------------------------------------------------
function Accordion({ title, defaultOpen = false, badge, children }: {
  title: string; defaultOpen?: boolean; badge?: ReactNode; children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-[26px] border transition-colors" style={{ background: CARD, borderColor: LINE }}>
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left rounded-[26px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
        <span className="flex items-center gap-2.5 min-w-0">
          <h2 className="text-[20px] font-bold tracking-tight truncate" style={{ ...SANS, color: INK }}>{title}</h2>
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

// Botón "ver más / ver menos" — el mismo gesto en toda la página.
function VerMas({ open, onClick, more, color }: { open: boolean; onClick: () => void; more?: number; color: string }) {
  return (
    <button onClick={onClick}
      className="mt-3 self-start inline-flex items-center gap-1 text-xs font-medium hover:opacity-70 transition-opacity focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)] rounded"
      style={{ color }}>
      {open ? "Ver menos" : more ? `Ver ${more} más` : "Ver más"}
      <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
    </button>
  )
}

// Severidad de riesgos → color por hex.
const SEV_HEX: Record<string, { color: string; label: string }> = {
  alta: { color: RED, label: "Alta" },
  media: { color: AMBER, label: "Media" },
  baja: { color: "#6C6A66", label: "Baja" },
}
const sevHex = (s: string) => SEV_HEX[s] ?? SEV_HEX.media
const SEV_ORDER: Record<string, number> = { alta: 0, media: 1, baja: 2 }

// --- Resumen ejecutivo: el titular. Recuadro navy como el Inicio, con "ver más".
function ResumenEjecutivo({ body }: { body: string }) {
  const [open, setOpen] = useState(false)
  const paras = body.split("\n").map(p => p.trim()).filter(Boolean)
  const oneLine = paras.join(" ")
  const long = oneLine.length > 320 || paras.length > 2
  return (
    <section className="rounded-[26px] p-6 text-white" style={{ background: BNAVY }}>
      <p className="mb-2 text-[10.5px] font-extrabold uppercase tracking-[0.17em] text-white/60">Resumen ejecutivo</p>
      {open ? (
        <div className="space-y-2">
          {paras.map((p, i) => <p key={i} className="text-[16px] leading-relaxed text-white/90">{p}</p>)}
        </div>
      ) : (
        <p className="text-[16px] leading-relaxed text-white/90 line-clamp-4">{oneLine}</p>
      )}
      {long && <VerMas open={open} onClick={() => setOpen(o => !o)} color="rgba(255,255,255,0.75)" />}
    </section>
  )
}

// --- Cifra compacta (una línea) --------------------------------------------
function Cifra({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <b className="text-[19px] font-bold tabular-nums" style={{ color }}>{value}</b>
      <span className="text-[14px] font-medium" style={{ color: MUTED }}>{label}</span>
    </span>
  )
}

// --- Bloque interno compacto (Fortalezas / Debilidades) --------------------
type Cubi = { area: string; tipo: string; texto: string }
function InternalBlock({ title, Icon, color, items }: {
  title: string; Icon: typeof TrendingUp; color: string; items: Cubi[]
}) {
  const [open, setOpen] = useState(false)
  if (items.length === 0) return null
  const CAP = 4
  const shown = open ? items : items.slice(0, CAP)
  const more = items.length - CAP
  return (
    <section className="rounded-[26px] p-5 flex flex-col" style={{ background: CARD, border: `1px solid ${LINE}` }}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className="h-4 w-4" style={{ color }} />
        <h3 className="text-[20px] font-bold tracking-tight" style={{ ...SANS, color: INK }}>{title}</h3>
        <span className="ml-auto text-xs font-bold tabular-nums" style={{ color, opacity: 0.55 }}>{items.length}</span>
      </div>
      <ul className="space-y-2.5 flex-1">
        {shown.map((h, i) => (
          <li key={i} className="flex gap-2 text-[16px] text-[var(--gob-charcoal)]">
            <span className="mt-2 h-1 w-1 rounded-full shrink-0" style={{ backgroundColor: color }} />
            <span className={`leading-snug ${open ? "" : "line-clamp-2"}`}>{h.texto}</span>
          </li>
        ))}
      </ul>
      {more > 0 && <VerMas open={open} onClick={() => setOpen(o => !o)} more={more} color={color} />}
    </section>
  )
}

// Los hallazgos internos (fortalezas/debilidades) se OCULTAN de la vista por
// pedido del cliente — los datos siguen viniendo del API porque la IA los usa.
// Cambiar a true para volver a mostrarlos.
const MOSTRAR_INTERNOS = false

// --- Riesgos compacto (color por severidad) --------------------------------
function RiesgosBlock({ riesgos }: { riesgos: { riesgo: string; severidad: string }[] }) {
  const [open, setOpen] = useState(false)
  if (riesgos.length === 0) return null
  const CAP = 5
  const shown = open ? riesgos : riesgos.slice(0, CAP)
  const more = riesgos.length - CAP
  return (
    <section className="rounded-[26px] p-5 flex flex-col" style={{ background: CARD, border: `1px solid ${LINE}` }}>
      <div className="flex items-center gap-2 mb-3">
        <ShieldAlert className="h-4 w-4" style={{ color: AMBER }} />
        <h3 className="text-[20px] font-bold tracking-tight" style={{ ...SANS, color: INK }}>Riesgos</h3>
        <span className="ml-auto text-xs font-bold tabular-nums" style={{ color: AMBER, opacity: 0.55 }}>{riesgos.length}</span>
      </div>
      <ul className="space-y-2.5 flex-1">
        {shown.map((r, i) => {
          const m = sevHex(r.severidad)
          return (
            <li key={i} className="flex gap-2 text-[16px] text-[var(--gob-charcoal)]">
              <span className="mt-1.5 h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: m.color }} title={m.label} />
              <span className={`leading-snug ${open ? "" : "line-clamp-2"}`}>
                {r.riesgo}
                <span className="ml-1.5 text-[10px] font-medium uppercase tracking-wide" style={{ color: m.color }}>· {m.label}</span>
              </span>
            </li>
          )
        })}
      </ul>
      {more > 0 && <VerMas open={open} onClick={() => setOpen(o => !o)} more={more} color={AMBER} />}
    </section>
  )
}

// --- Oportunidades para la empresa (del cuadrante Oportunidades del FODA) ---
function OportunidadesBlock({ items }: { items: string[] }) {
  const [open, setOpen] = useState(false)
  if (items.length === 0) return null
  const CAP = 5
  const shown = open ? items : items.slice(0, CAP)
  const more = items.length - CAP
  return (
    <section className="rounded-[26px] p-5 flex flex-col" style={{ background: CARD, border: `1px solid ${LINE}` }}>
      <div className="flex items-center gap-2 mb-3">
        <Compass className="h-4 w-4" style={{ color: BNAVY }} />
        <h3 className="text-[20px] font-bold tracking-tight" style={{ ...SANS, color: INK }}>Oportunidades</h3>
        <span className="ml-auto text-xs font-bold tabular-nums" style={{ color: BNAVY, opacity: 0.55 }}>{items.length}</span>
      </div>
      <ul className="space-y-2.5 flex-1">
        {shown.map((o, i) => (
          <li key={i} className="flex gap-2 text-[16px] text-[var(--gob-charcoal)]">
            <span className="mt-2 h-1 w-1 rounded-full shrink-0" style={{ backgroundColor: BNAVY }} />
            <span className={`leading-snug ${open ? "" : "line-clamp-2"}`}>{o}</span>
          </li>
        ))}
      </ul>
      {more > 0 && <VerMas open={open} onClick={() => setOpen(o => !o)} more={more} color={BNAVY} />}
    </section>
  )
}

// --- FODA 2×2: el protagonista ---------------------------------------------
// Arriba Fortalezas | Oportunidades, abajo Debilidades | Amenazas.
// Cada cuadrante con su color al ~8% de fondo, acento sólido, y "ver más" propio.
type QuadDef = { key: keyof Foda; label: string; sub: string; color: string; Icon: typeof TrendingUp }
const FODA_QUADS: QuadDef[] = [
  { key: "fortalezas", label: "Fortalezas", sub: "Interno · a favor", color: GREEN, Icon: TrendingUp },
  { key: "oportunidades", label: "Oportunidades", sub: "Externo · a favor", color: BNAVY, Icon: Compass },
  { key: "debilidades", label: "Debilidades", sub: "Interno · en contra", color: AMBER, Icon: AlertTriangle },
  { key: "amenazas", label: "Amenazas", sub: "Externo · en contra", color: RED, Icon: ShieldAlert },
]

function FodaQuadrant({ def, items }: { def: QuadDef; items: string[] }) {
  const [open, setOpen] = useState(false)
  const CAP = 4
  const shown = open ? items : items.slice(0, CAP)
  const more = items.length - CAP
  const { color, Icon } = def
  return (
    <div className="rounded-[26px] p-5 flex flex-col" style={{ backgroundColor: `${color}14`, border: `1px solid ${color}22` }}>
      <div className="flex items-center gap-2.5 mb-3">
        <span className="h-8 w-8 rounded-lg flex items-center justify-center shrink-0" style={{ backgroundColor: color }}>
          <Icon className="h-4 w-4 text-white" />
        </span>
        <div className="min-w-0">
          <h3 className="text-[20px] font-bold tracking-tight" style={{ ...SANS, color }}>{def.label}</h3>
          <p className="text-[10px] font-medium uppercase tracking-[0.14em]" style={{ color, opacity: 0.6 }}>{def.sub}</p>
        </div>
        <span className="ml-auto text-xs font-bold tabular-nums" style={{ color, opacity: 0.5 }}>{items.length}</span>
      </div>
      {items.length > 0 ? (
        <ul className="space-y-2 flex-1">
          {shown.map((t, i) => (
            <li key={i} className="flex gap-2 text-[16px] text-[var(--gob-charcoal)]">
              <span className="mt-2 h-1 w-1 rounded-full shrink-0" style={{ backgroundColor: color }} />
              <span className={`leading-snug ${open ? "" : "line-clamp-2"}`}>{t}</span>
            </li>
          ))}
        </ul>
      ) : <p className="text-xs text-gray-400 italic flex-1">Sin elementos.</p>}
      {more > 0 && <VerMas open={open} onClick={() => setOpen(o => !o)} more={more} color={color} />}
    </div>
  )
}

function FodaSection({ foda }: { foda: Foda }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <LayoutGrid className="h-4 w-4" style={{ color: BNAVY }} />
        <h2 className="text-[23px] font-bold leading-tight tracking-[-.025em]" style={{ ...SANS, color: INK }}>Matriz FODA</h2>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {FODA_QUADS.map(def => (
          <FodaQuadrant key={def.key} def={def} items={(foda[def.key] as string[]) || []} />
        ))}
      </div>
      {foda.sintesis && (
        <div className="rounded-[26px] p-6 text-white" style={{ background: BNAVY }}>
          <p className="mb-2 text-[10.5px] font-extrabold tracking-[0.17em] uppercase text-white/60">Síntesis</p>
          <p className="text-[16px] leading-relaxed text-white/90">{foda.sintesis}</p>
        </div>
      )}
    </section>
  )
}

export default function DiagnosticoPage() {
  const [view, setView] = useState<View>("loading")
  const [diag, setDiag] = useState<Diagnostico | null>(null)
  const [foda, setFoda] = useState<FodaOut | null>(null)
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

  // El FODA ahora es una sección del Diagnóstico. Lo traemos con el mismo fetch
  // que ya usa la app; si sigue generándose, reintentamos hasta que esté listo.
  useEffect(() => {
    let alive = true
    let t: ReturnType<typeof setTimeout> | null = null
    const tick = async () => {
      try {
        const d = await getFoda()
        if (!alive) return
        setFoda(d)
        if (d.status === "generating") t = setTimeout(tick, 4000)
      } catch { /* reintenta al recargar */ }
    }
    tick()
    return () => { alive = false; if (t) clearTimeout(t) }
  }, [])

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
    return <div className="min-h-dvh flex items-center justify-center" style={{ background: PAPER }}>
      <Loader2 className="h-5 w-5 animate-spin text-gray-300" />
    </div>
  }

  if (view === "generating") {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center gap-6 px-6 text-center" style={{ background: PAPER }}>
        <Loader2 className="h-6 w-6 animate-spin" style={{ color: BNAVY }} />
        <div className="space-y-1">
          <p className="text-[10.5px] font-extrabold tracking-[0.17em] uppercase" style={{ color: ACCENT }}>Investigando</p>
          <h1 className="text-2xl font-bold" style={{ ...SANS, color: INK }}>Tu Consejo está investigando tu empresa en la web</h1>
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
      <div className="min-h-dvh flex flex-col items-center justify-center gap-6 px-6 text-center" style={{ background: PAPER }}>
        <div className="w-14 h-14 rounded-[20px] border-2 border-gray-100 flex items-center justify-center">
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
            className="inline-flex items-center gap-2 rounded-full bg-[#FF5C1A] text-white text-[13px] font-bold tracking-wide px-5 py-3 hover:bg-[#e64f12] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
            Completar mis datos
          </Link>
        ) : (
          <button onClick={onGenerate}
            className="inline-flex items-center gap-2 rounded-full bg-[#FF5C1A] text-white text-[13px] font-bold tracking-wide px-5 py-3 hover:bg-[#e64f12] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
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
  const allSections = (diag?.sections ?? []).filter(s => s.body)
  const resumen = allSections.find(s => s.key === RESUMEN_KEY)
  const contextSections = allSections.filter(s => s.key !== RESUMEN_KEY)
  const sinInterno = fortalezas.length === 0 && debilidades.length === 0 && riesgos.length === 0
  const hayCifras = fortalezas.length > 0 || debilidades.length > 0 || riesgos.length > 0
  const fodaActivo = foda?.status === "active" && !!foda.foda
  // Oportunidades para la empresa: salen del cuadrante Oportunidades del FODA.
  const oportunidades = fodaActivo ? (foda!.foda!.oportunidades ?? []).filter(Boolean) : []

  return (
    <div className="min-h-dvh text-black antialiased" style={{ background: PAPER }}>
      <main>
        <PageShell className="py-8">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE }}
            className="space-y-6"
          >

            {/* Header bento — todo en Inter, sin barra sticky, igual que el Inicio */}
            <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
              <div>
                <p className="text-[10.5px] font-extrabold uppercase tracking-[0.17em]" style={{ color: MUTED }}>Diagnóstico estratégico</p>
                <h1 className="mt-1 text-[32px] font-bold leading-[1.05] tracking-[-.03em]" style={{ ...SANS, color: INK }}>La realidad de tu empresa</h1>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <button onClick={onDownload} disabled={downloading}
                  className="inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-[13px] font-medium text-gray-700 transition-colors disabled:opacity-50 hover:border-[#0E1626] hover:text-[#0E1626] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]"
                  style={{ borderColor: LINE }}>
                  {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                  PDF
                </button>
                <a href="/onboarding/todd/externo"
                  className="inline-flex items-center gap-2 rounded-full bg-[#FF5C1A] px-5 py-3 text-[13px] font-bold tracking-wide text-white transition-colors hover:bg-[#e64f12] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
                  <span className="hidden sm:inline">Continuar al análisis del entorno</span>
                  <span className="sm:hidden">Continuar</span>
                  <ArrowRight className="h-4 w-4" />
                </a>
              </div>
            </div>

            {/* 1 · Resumen ejecutivo: lo primero que lee el dueño */}
            {resumen && <ResumenEjecutivo body={resumen.body} />}

            {/* 2 · Cifras de un vistazo — una línea */}
            {hayCifras && (
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-[26px] px-5 py-3.5 text-sm" style={{ background: SAND, border: `1px solid ${LINE}` }}>
                <Cifra value={fortalezas.length} label="Fortalezas" color={GREEN} />
                <Cifra value={debilidades.length} label="Debilidades" color={RED} />
                <Cifra value={riesgos.length} label="Riesgos" color={AMBER} />
                <Cifra value={sources.length} label="Fuentes" color={BNAVY} />
              </div>
            )}

            {/* 3 · FODA 2×2 — el protagonista */}
            {fodaActivo && <FodaSection foda={foda!.foda!} />}

            {/* 4 · Riesgos + Oportunidades (los hallazgos internos quedan
                ocultos con MOSTRAR_INTERNOS; la IA sigue usando esos datos) */}
            {sinInterno && oportunidades.length === 0 ? (
              <p className="text-[16px]" style={{ color: MUTED }}>
                Aún no hay hallazgos internos. Complétalos platicando con Todd — abajo tienes el contexto de mercado.
              </p>
            ) : (
              <div className={`grid gap-4 lg:items-start ${MOSTRAR_INTERNOS ? "lg:grid-cols-3" : "lg:grid-cols-2"}`}>
                {MOSTRAR_INTERNOS && <InternalBlock title="Fortalezas internas" Icon={TrendingUp} color={GREEN} items={fortalezas} />}
                {MOSTRAR_INTERNOS && <InternalBlock title="Debilidades internas" Icon={TrendingDown} color={RED} items={debilidades} />}
                <RiesgosBlock riesgos={riesgos} />
                <OportunidadesBlock items={oportunidades} />
              </div>
            )}

            {/* 5 · Respaldo: contexto de mercado y fuentes, colapsados al final */}
            {(contextSections.length > 0 || sources.length > 0) && (
              <div className="space-y-3 pt-2">
                {contextSections.length > 0 && (
                  <Accordion title="Contexto de mercado" defaultOpen={sinInterno} badge={
                    <span className="inline-flex items-center gap-1 text-[11px] text-gray-400">
                      <Globe className="h-3 w-3" /> investigación web
                    </span>
                  }>
                    {/* Cada sub-tema en su propia tarjeta (divisiones bento) con color-coded markers en los párrafos */}
                    <div className="grid gap-3 md:grid-cols-2">
                      {contextSections.map(s => (
                        <div key={s.key} className="rounded-[26px] p-5" style={{ background: SAND }}>
                          <h3 className="text-[20px] font-bold leading-tight tracking-[-.02em]" style={{ ...SANS, color: INK }}>{s.title}</h3>
                          <div className="mt-3 space-y-3">
                            {s.body.split("\n").filter(p => p.trim()).map((p, j) => {
                              const markerColor = j % 2 === 0 ? BNAVY : ACCENT
                              return (
                                <div key={j} className="flex gap-3">
                                  <span className="mt-1.5 h-2 w-2 rounded-full shrink-0" style={{ background: markerColor }} />
                                  <p className="text-[16px] leading-relaxed" style={{ color: INK2 }}>{p.trim()}</p>
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </Accordion>
                )}

                {sources.length > 0 && (
                  <Accordion title="Fuentes" badge={
                    <span className="text-xs font-medium text-gray-400 rounded-full px-2 py-0.5" style={{ background: SAND }}>{sources.length}</span>
                  }>
                    <ul className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
                      {sources.map((src, i) => (
                        <li key={i} className="flex items-start gap-2 text-[13px] text-gray-500">
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
              </div>
            )}

            {/* Pie: regenerar + continuar */}
            <div className="pt-4 flex items-center justify-between gap-4 flex-wrap border-t" style={{ borderColor: LINE }}>
              <button onClick={onGenerate}
                className="text-xs font-medium text-gray-400 hover:text-[var(--gob-navy)] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)] rounded">
                Regenerar diagnóstico
              </button>
              <a href="/onboarding/todd/externo"
                className="inline-flex items-center gap-2 rounded-full bg-[#FF5C1A] text-white text-[13px] font-bold tracking-wide px-5 py-3 hover:bg-[#e64f12] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
                Continuar al análisis del entorno <ArrowRight className="h-4 w-4" />
              </a>
            </div>

          </motion.div>
        </PageShell>
      </main>
    </div>
  )
}
