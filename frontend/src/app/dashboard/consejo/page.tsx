"use client"

import { useEffect, useState, type CSSProperties } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import {
  ArrowRight, ArrowUpRight, Play, X, Loader2, Sparkles, ChevronRight, FileText,
} from "lucide-react"
import { useOnboardingStore } from "@/lib/store"
import { PageShell, PageHeader, Prose } from "@/components/ui/PageShell"
import TableroPlan from "@/components/consejo/TableroPlan"
import OrdenDelDiaCadena from "@/components/consejo/OrdenDelDiaCadena"
import api from "@/lib/api"
import { downloadSesionActaPdf, getBoard, type BoardMes } from "@/lib/board"
import { getRoadmap, type Roadmap } from "@/lib/roadmap"
import { aniosDelPlan } from "@/components/roadmap/shared"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// Paleta bento — color tokens del sistema de diseño
const PAPER = "#F2F2F0"
const INK   = "#0E1626"
const INK2  = "#39435A"
const MUTED = "#6E7686"
const CARD  = "#FFFFFF"
const SAND  = "#E8E3D8"
const BNAVY = "#152742"
const ACCENT = "#FF5C1A"
const LINE  = "#E2E2DC"
const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }

const ETAPAS = [
  { n: 1, label: "Empresa" }, { n: 2, label: "Equipo" }, { n: 3, label: "Prioridades" },
  { n: 4, label: "Diagnóstico" }, { n: 5, label: "Indicadores" }, { n: 6, label: "Gobierno" },
  { n: 7, label: "Documentos" }, { n: 8, label: "Visión" },
]

const MONTH_NAMES = [
  "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

interface BoardSession {
  board_session_id: string
  period_year: number
  period_month: number
  // Sesiones antiguas pueden no traer estos campos: se toleran ausentes.
  period_label?: string
  status?: string
  message_count?: number
}

const STATUS_LABEL: Record<string, string> = {
  draft: "Borrador", active: "Activa", completed: "Completada",
}

export default function ConsejoPage() {
  const router = useRouter()
  const { completedStages, hydrate, reset } = useOnboardingStore()

  const [sessions, setSessions] = useState<BoardSession[]>([])
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null)
  // Los meses del Plan anual: son las únicas fechas sesionables en el modal.
  const [meses, setMeses] = useState<BoardMes[]>([])
  const [showSetupModal, setShowSetupModal] = useState(false)
  const [showModal, setShowModal] = useState(false)
  // Periodo que se está creando ("year-month"), para el spinner de esa fila.
  const [creatingKey, setCreatingKey] = useState<string | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
  // Id de la sesión cuyo acta se está descargando (para el spinner del botón).
  const [downloadingActa, setDownloadingActa] = useState<string | null>(null)

  async function handleDownloadActa(e: React.MouseEvent, sessionId: string) {
    // La tarjeta es un Link: evitamos que el click navegue a la sesión.
    e.preventDefault()
    e.stopPropagation()
    if (downloadingActa) return
    setDownloadingActa(sessionId)
    try {
      await downloadSesionActaPdf(sessionId)
    } catch {
      // Silencioso: si el acta no se puede generar aún, no rompemos la vista.
    } finally {
      setDownloadingActa(null)
    }
  }

  useEffect(() => {
    api.get("/onboarding/my-session")
      .then(r => {
        const sid = r.data?.session_id
        if (sid) hydrate(sid, r.data.completed_stages ?? [])
        else reset()
      })
      .catch(() => {})
    api.get("/board-sessions").then(r => setSessions(r.data)).catch(() => {})
    getRoadmap().then(r => setRoadmap(r)).catch(() => {})
    getBoard().then(setMeses).catch(() => {})

    // Deep-link desde "Mis consejeros": /dashboard/consejo?sesionar=1 abre
    // directo el selector de periodo de la nueva sesión. setState diferido a un
    // microtask para no disparar renders en cascada (regla set-state-in-effect).
    if (new URLSearchParams(window.location.search).get("sesionar") === "1") {
      queueMicrotask(() => setShowModal(true))
    }
  }, [hydrate, reset])

  const onboardingComplete = completedStages.length >= 8
  const nextEtapa = ETAPAS.find(e => !completedStages.includes(e.n))
  const [currentYear] = roadmap ? aniosDelPlan(roadmap.anio_objetivo) : [new Date().getFullYear()]
  // Año del plan (para la sesión de TODO el plan): el del primer mes sesionable.
  const planYear = meses[0]?.period_year ?? currentYear

  const openModal = () => {
    setCreateError(null)
    setShowModal(true)
  }

  const tryCreateSession = () => {
    if (onboardingComplete) openModal()
    else setShowSetupModal(true)
  }

  /** Busca la sesión ya creada de un periodo (para mostrar su estado y reabrirla). */
  const sesionDe = (y: number, m: number) =>
    sessions.find(s => s.period_year === y && s.period_month === m)

  /** Crea (o reabre, vía 409) la sesión del periodo. month=0 → todo el plan. */
  const createSession = async (y: number, m: number) => {
    setCreatingKey(`${y}-${m}`)
    setCreateError(null)
    try {
      const r = await api.post("/board-sessions", { period_year: y, period_month: m })
      setShowModal(false)
      router.push(`/dashboard/sesion/${r.data.board_session_id}`)
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        const existing = sesionDe(y, m)
        if (existing) {
          setShowModal(false)
          router.push(`/dashboard/sesion/${existing.board_session_id}`)
          return
        }
      }
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setCreateError(typeof msg === "string" ? msg : "No se pudo crear la sesión. Intenta de nuevo.")
    } finally {
      setCreatingKey(null)
    }
  }

  return (
    <div className="min-h-dvh font-sans antialiased" style={{ background: PAPER, color: INK }}>
      {/* Setup-required modal */}
      <AnimatePresence>
        {showSetupModal && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }} className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
              onClick={() => setShowSetupModal(false)} />
            <motion.div initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }} transition={{ duration: 0.25, ease: EASE }}
              className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto rounded-[26px] shadow-xl p-8 space-y-5" style={{ background: CARD }}>
              <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ background: SAND }}>
                <Sparkles className="h-5 w-5" style={{ color: INK }} />
              </div>
              <div className="space-y-2">
                <h2 className="text-lg font-bold" style={{ ...SANS, color: INK }}>Configura tu empresa primero</h2>
                <p className="text-sm leading-relaxed" style={{ color: INK2 }}>
                  Para que el Consejo de IA te entregue análisis útiles, necesitamos conocer tu empresa: industria, equipo, prioridades, Indicadores y gobierno. Toma unos minutos y solo se hace una vez. Después podrás iniciar sesiones cuando quieras.
                </p>
              </div>
              {!onboardingComplete && completedStages.length > 0 && (
                <div className="rounded-[20px] p-3" style={{ background: SAND }}>
                  <p className="text-xs" style={{ color: MUTED }}>
                    Vas en {completedStages.length} de 8 etapas
                    {nextEtapa && ` · siguiente: ${nextEtapa.label}`}
                  </p>
                </div>
              )}
              <div className="flex gap-2">
                <button onClick={() => setShowSetupModal(false)}
                  className="flex-1 text-sm font-medium transition-colors hover:opacity-70" style={{ color: INK2 }}>
                  Más tarde
                </button>
                <Link href="/onboarding/todd"
                  className="flex-[2] inline-flex items-center justify-center gap-2 text-sm font-medium py-3 rounded-[20px] transition-colors" style={{ background: BNAVY, color: CARD }}>
                  {completedStages.length > 0 ? "Continuar configuración" : "Empezar"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Nueva sesión modal */}
      <AnimatePresence>
        {showModal && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }} className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
              onClick={() => setShowModal(false)} />
            <motion.div initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }} transition={{ duration: 0.25, ease: EASE }}
              className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto rounded-[26px] shadow-xl p-8 space-y-6" style={{ background: CARD }}>
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-bold" style={{ ...SANS, color: INK }}>Nueva sesión de Consejo</h2>
                  <p className="text-xs mt-0.5" style={{ color: MUTED }}>Los meses de tu Plan anual — pasados, en curso y por venir</p>
                </div>
                <button onClick={() => setShowModal(false)} className="transition-colors hover:opacity-70" style={{ color: MUTED }}>
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Sesión de TODO el plan (año completo) */}
              <button
                type="button"
                onClick={() => createSession(planYear, 0)}
                disabled={creatingKey !== null}
                className="w-full flex items-center justify-between gap-3 rounded-[20px] px-4 py-3.5 text-sm font-bold text-white transition-colors hover:brightness-90 disabled:opacity-50"
                style={{ ...SANS, background: BNAVY }}
              >
                <span className="text-left">
                  Sesionar todo el plan
                  <span className="block text-[11px] font-medium" style={{ color: "rgba(255,255,255,.65)" }}>
                    El Consejo revisa el año {planYear} completo
                  </span>
                </span>
                {creatingKey === `${planYear}-0`
                  ? <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
                  : <ArrowRight className="h-4 w-4 shrink-0" />}
              </button>

              {/* Meses del plan */}
              {meses.length > 0 ? (
                <div className="space-y-1.5 max-h-[46vh] overflow-y-auto pr-1">
                  {meses.map(mes => {
                    const existente = sesionDe(mes.period_year, mes.period_month)
                    const key = `${mes.period_year}-${mes.period_month}`
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => createSession(mes.period_year, mes.period_month)}
                        disabled={creatingKey !== null}
                        className="w-full flex items-center justify-between gap-3 rounded-[16px] border px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50"
                        style={{ borderColor: mes.es_mes_actual ? BNAVY : LINE, color: INK2, background: CARD }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = BNAVY; e.currentTarget.style.color = BNAVY }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = mes.es_mes_actual ? BNAVY : LINE; e.currentTarget.style.color = INK2 }}
                      >
                        <span className="flex items-center gap-2.5">
                          {mes.label}
                          {mes.es_mes_actual && (
                            <span className="text-[10px] font-extrabold uppercase tracking-[0.09em]" style={{ color: ACCENT }}>
                              Mes en curso
                            </span>
                          )}
                        </span>
                        {creatingKey === key
                          ? <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
                          : existente
                            ? <span className="text-[11px] font-bold" style={{ color: MUTED }}>{STATUS_LABEL[existente.status ?? ""] ?? "Abrir"}</span>
                            : <ArrowRight className="h-4 w-4 shrink-0" style={{ color: MUTED }} />}
                      </button>
                    )
                  })}
                </div>
              ) : (
                <p className="text-xs leading-relaxed" style={{ color: MUTED }}>
                  Aún no hay meses sesionables: aprueba tu Plan anual para que aparezcan aquí.
                </p>
              )}

              {createError && <p className="text-xs" style={{ color: "#dc2626" }}>{createError}</p>}
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <PageHeader
        eyebrow="Centro de operaciones"
        title="Tareas"
        actions={
          <button onClick={tryCreateSession}
            className="inline-flex items-center gap-2 text-sm font-medium px-4 py-2.5 rounded-[20px] transition-colors" style={{ background: BNAVY, color: CARD }}>
            Nueva sesión <ChevronRight className="h-3.5 w-3.5" />
          </button>
        }
      />

      <main>
        <PageShell className="py-10 space-y-12">

          {/* ── Tablero del plan (protagonista, a todo lo ancho) ──────────── */}
          <section className="space-y-5">
            <Prose>
              <p className="text-sm leading-relaxed" style={{ color: INK2 }}>
                Aquí operas mes a mes las tareas de tu plan: quién responde, en qué van y cuándo vencen.
                Sesiona cualquier mes para que el Consejo lo evalúe, o pregúntale a Todd (el botón
                flotante) qué está atrasado.
              </p>
            </Prose>
            <TableroPlan />
          </section>

          {/* ── Orden del día: la cadena, armada desde el Plan anual ──────── */}
          <OrdenDelDiaCadena />

          {/* ── Sesiones de consejo ──────────────────────── */}
          <section className="space-y-5">
            <div>
              <p className="text-xs font-medium tracking-widest uppercase mb-1" style={{ color: MUTED }}>Historial</p>
              <h2 className="text-2xl font-bold tracking-tight" style={{ ...SANS, color: INK }}>Sesiones de Consejo</h2>
            </div>

            {sessions.length > 0 ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-3">
                {sessions.map((s, i) => (
                  <motion.div key={s.board_session_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, ease: EASE, delay: i * 0.04 }}
                    className="relative">
                    <Link href={`/dashboard/sesion/${s.board_session_id}`}
                      className="group h-full flex items-center justify-between gap-4 pl-5 pr-24 py-4 rounded-[26px] transition-all duration-200 hover:shadow-sm" style={{ background: CARD, border: `1px solid ${LINE}` }}>
                      <div className="flex items-center gap-4 min-w-0">
                        <span className="w-10 h-10 rounded-[16px] border-2 flex items-center justify-center shrink-0 transition-colors" style={{ borderColor: LINE }}>
                          <span className="text-xs font-bold" style={{ color: MUTED }}>
                            {s.period_month === 0 ? "Año" : MONTH_NAMES[s.period_month]?.slice(0, 3)}
                          </span>
                        </span>
                        <span className="min-w-0">
                          <span className="block text-sm font-medium truncate" style={{ color: INK }}>
                            {s.period_label ?? (s.period_month === 0 ? `Todo el plan · ${s.period_year}` : `${MONTH_NAMES[s.period_month]} ${s.period_year}`)}
                          </span>
                          <span className="block text-xs mt-0.5" style={{ color: MUTED }}>
                            {STATUS_LABEL[s.status ?? ""] ?? "Borrador"}
                            {(s.message_count ?? 0) > 0 && ` · ${s.message_count} mensajes`}
                          </span>
                        </span>
                      </div>
                      <ArrowUpRight className="h-4 w-4 transition-colors shrink-0" style={{ color: LINE }} />
                    </Link>
                    {/* Acta histórica: foto inmutable de la sesión. Fuera del <Link> para no
                        anidar botón en <a>; el handler igual frena la navegación. */}
                    <button type="button"
                      onClick={(e) => handleDownloadActa(e, s.board_session_id)}
                      disabled={downloadingActa === s.board_session_id}
                      title="Descargar acta (PDF)"
                      className="absolute right-11 top-1/2 -translate-y-1/2 inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1.5 rounded-[12px] transition-all duration-150 disabled:opacity-60" style={{ background: CARD, border: `1px solid ${LINE}`, color: MUTED }} onMouseEnter={(e) => { e.currentTarget.style.borderColor = BNAVY; e.currentTarget.style.color = BNAVY }} onMouseLeave={(e) => { e.currentTarget.style.borderColor = LINE; e.currentTarget.style.color = MUTED }}>
                      {downloadingActa === s.board_session_id
                        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        : <FileText className="h-3.5 w-3.5" />}
                      Acta
                    </button>
                  </motion.div>
                ))}
              </div>
            ) : (
              <div className="rounded-[26px] p-12 flex flex-col items-center justify-center text-center gap-3" style={{ background: CARD, border: `1px solid ${LINE}` }}>
                <span className="w-12 h-12 rounded-full border-2 flex items-center justify-center" style={{ borderColor: LINE }}>
                  <Play className="h-5 w-5" style={{ color: LINE }} />
                </span>
                <p className="text-sm font-medium" style={{ color: INK }}>
                  {onboardingComplete ? "Aún no hay sesiones" : "Completa la configuración primero"}
                </p>
                <p className="text-xs max-w-sm leading-relaxed" style={{ color: INK2 }}>
                  {onboardingComplete
                    ? "Convoca a tu primera sesión: los consejeros revisarán tu empresa y los documentos que subas."
                    : "Cuando termines de configurar tu empresa, tus consejeros podrán generar el primer análisis."}
                </p>
                <button onClick={tryCreateSession}
                  className="inline-flex items-center gap-2 text-xs font-medium px-4 py-2.5 rounded-[20px] transition-all duration-150 mt-1" style={{ border: `1px solid ${LINE}`, color: INK2 }} onMouseEnter={(e) => { e.currentTarget.style.borderColor = BNAVY; e.currentTarget.style.color = BNAVY }} onMouseLeave={(e) => { e.currentTarget.style.borderColor = LINE; e.currentTarget.style.color = INK2 }}>
                  Convocar sesión <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </section>

        </PageShell>
      </main>
    </div>
  )
}
